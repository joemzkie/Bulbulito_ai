import json
import logging
import re
from collections.abc import Callable

from pydantic import ValidationError

from app.providers.client import call_chatbot
from .config import DEPTH_CONFIG, RIZARTS_PROFILE
from . import prompts
from .retriever import WebRetrievalError, search_web
from .schemas import AuditOutput, ExtractorOutput, PlannerOutput, VerifiedSource
from .validators import parse_strict_json, validate_audit, validate_citations, validate_claim_sources, validate_planner_count

logger = logging.getLogger("bulbulito.research")
Progress = Callable[[str], None]


class ResearchPipelineError(Exception):
    """Safe user-facing failure for a RIZARTS pipeline that cannot ground its report."""


def _json_stage(stage: str, system: str, user: str, schema, model_key: str):
    last_error = None
    correction = ""
    for attempt in range(2):
        raw = call_chatbot(model_key, [
            {"role": "system", "content": system},
            {"role": "user", "content": user + correction},
        ], temperature=0.1)
        try:
            return parse_strict_json(raw, schema)
        except (ValueError, TypeError, ValidationError) as exc:
            last_error = exc
            correction = "\n\nThe previous response was invalid. Return one valid JSON object matching the required schema only."
    logger.warning("RIZARTS stage validation failed: stage=%s error_type=%s", stage, type(last_error).__name__)
    raise ResearchPipelineError(f"RIZARTS could not validate its {stage} output. Please try again.")


def _plan(topic: str, depth: str, constraints: str | None, context: str) -> list:
    depth_settings = DEPTH_CONFIG[depth]
    min_count, max_count = depth_settings["query_counts"]
    user = (
        f"Research topic:\n{topic}\n\nResearch depth:\n{depth}\n\n"
        f"Additional constraints:\n{constraints or 'None'}\n\n"
        f"Relevant prior conversation context:\n{context or 'None'}\n\n"
        f"Generate {min_count} to {max_count} orthogonal search queries."
    )
    last_error = None
    correction = ""
    for _ in range(2):
        raw = call_chatbot(RIZARTS_PROFILE["planner_model"], [
            {"role": "system", "content": prompts.PLANNER_SYSTEM},
            {"role": "user", "content": user + correction},
        ], temperature=0.1)
        try:
            result = parse_strict_json(raw, PlannerOutput)
            validate_planner_count(len(result.queries), min_count, max_count)
            values = [item.query.casefold().strip() for item in result.queries]
            if len(set(values)) != len(values):
                raise ValueError("Planner returned duplicate queries.")
            return result.queries
        except (ValueError, TypeError, ValidationError) as exc:
            last_error = exc
            correction = f"\n\nCorrect the previous response. Return {min_count}–{max_count} distinct queries as strict JSON only."
    logger.warning("RIZARTS stage validation failed: stage=planner error_type=%s", type(last_error).__name__)
    raise ResearchPipelineError("RIZARTS could not create a valid research plan. Please try again.")


def _extract(query: str, search_text: str, sources: list[VerifiedSource], offset: int = 0) -> list[dict]:
    if not sources:
        return []
    source_lines = [
        {
            "source_index": i,
            "title": source.title,
            "url": source.url,
            "snippet": source.content,
        }
        for i, source in enumerate(sources)
    ]
    user = (
        f"Sub-query:\n{query}\n\nSearch response:\n{search_text}\n\n"
        f"Verified sources (indexes are local to this query):\n{json.dumps(source_lines, ensure_ascii=False)}"
    )
    result = _json_stage("claim extraction", prompts.EXTRACTOR_SYSTEM, user, ExtractorOutput, RIZARTS_PROFILE["extractor_model"])
    validate_claim_sources(result.claims, sources)
    return [
        {**claim.model_dump(), "source_indexes": [index + offset for index in claim.source_indexes]}
        for claim in result.claims
    ]


def _retrieve(queries: list[str], all_sources: list[VerifiedSource], all_claims: list[dict], progress: Progress | None) -> int:
    added = 0
    for query in queries:
        try:
            search_text, found = search_web(query)
        except WebRetrievalError as exc:
            logger.warning("RIZARTS web retrieval failed: category=%s", exc.category)
            continue
        except Exception as exc:
            # Do not log exception text: SDK/network exceptions can include
            # request details. Continue other planned queries for transient or
            # query-specific failures.
            logger.warning("RIZARTS retrieval failed: category=unexpected error_type=%s", type(exc).__name__)
            continue
        if not found or not search_text.strip():
            continue
        if progress:
            progress("Extracting evidence...")
        # Claims may cite all evidence returned for this query, including sources
        # already in the dossier. Map local indexes to the deduplicated global list.
        mappings: list[int] = []
        for source in found:
            existing = next((i for i, current in enumerate(all_sources) if current.url == source.url), None)
            if existing is None:
                existing = len(all_sources)
                all_sources.append(source)
                added += 1
            mappings.append(existing)
        local_claims = _extract(query, search_text, found)
        for claim in local_claims:
            claim["source_indexes"] = sorted({mappings[index] for index in claim["source_indexes"]})
            all_claims.append(claim)
    return added


def _synthesize(topic: str, context: str, sources: list[VerifiedSource], claims: list[dict]) -> str:
    if not sources:
        raise ResearchPipelineError("RIZARTS could not retrieve verified sources, so it cannot provide a sourced research report.")
    dossier = {
        "conversation_context": context,
        "claims": claims,
        "sources": [{"title": s.title, "url": s.url, "query": s.query, "search_queries": s.search_queries, "citation_metadata": s.citation_metadata, "content": s.content} for s in sources],
    }
    verified_urls = {source.url: source.title for source in sources}
    correction = ""
    for attempt in range(2):
        answer = call_chatbot(RIZARTS_PROFILE["synthesizer_model"], [
            {"role": "system", "content": prompts.SYNTHESIZER_SYSTEM},
            {"role": "user", "content": f"Topic:\n{topic}\n\nResearch dossier:\n{json.dumps(dossier, ensure_ascii=False)}\n\nSource URL whitelist:\n{json.dumps(sorted(verified_urls))}{correction}"},
        ], temperature=0.2)
        try:
            validate_citations(answer, verified_urls)
            required_sections = ("# Executive Takeaway", "# Core Technical Analysis", "# Current Bottlenecks / Controversies", "# Conclusion", "## Sources")
            if not all(section in answer for section in required_sections):
                raise ValueError("Required report section is missing.")
            return answer
        except ValueError:
            if attempt == 0:
                correction = "\n\nThe prior draft failed validation. Rewrite it using only exact URLs from the whitelist and include every required section."
    logger.warning("RIZARTS citation validation failed; returning a clearly labeled uncited fallback")
    return _unverified_fallback(
        topic,
        context,
        "Live search results were available, but their citations could not be validated.",
    )


def _unverified_fallback(topic: str, context: str, limitation: str) -> str:
    """Return a useful, explicitly uncited answer without fabricating web evidence."""
    answer = call_chatbot(RIZARTS_PROFILE["synthesizer_model"], [
        {"role": "system", "content": prompts.UNVERIFIED_FALLBACK_SYSTEM},
        {"role": "user", "content": f"Topic:\n{topic}\n\nRelevant prior conversation context:\n{context or 'None'}"},
    ], temperature=0.2)
    # Keep this fallback unmistakably uncited even if the model ignores its prompt.
    answer = re.sub(r"\[([^\]]+)\]\((?:[^()]|\([^()]*\))*\)", r"\1", answer)
    answer = re.sub(r"https?://\S+", "", answer)
    return (
        f"> **Research limitation:** {limitation} This response is a best-effort answer from the model's general knowledge, not a web-verified report.\n\n"
        f"{answer.strip()}"
    )


def _audit(topic: str, claims: list[dict], draft: str) -> AuditOutput | None:
    try:
        result = _json_stage("quality audit", prompts.AUDITOR_SYSTEM,
            f"Initial topic:\n{topic}\n\nExtracted claims:\n{json.dumps(claims, ensure_ascii=False)}\n\nDraft synthesis:\n{draft}\n\nDetermine whether critical research gaps remain.",
            AuditOutput, RIZARTS_PROFILE["auditor_model"])
        validate_audit(result)
        return result
    except Exception as exc:
        # The synthesis has already passed citation validation. The audit is a
        # quality gate, but an unavailable auditor must not erase a valid report.
        logger.warning("RIZARTS audit failed: error_type=%s", type(exc).__name__)
        return None


def run_rizarts_research(
    topic: str,
    research_depth: str = "deep",
    constraints: str | None = None,
    conversation_history: list[dict] | None = None,
    progress: Progress | None = None,
) -> str:
    if research_depth not in DEPTH_CONFIG:
        raise ResearchPipelineError("Unsupported RIZARTS research depth.")
    context_messages = (conversation_history or [])[-12:]
    context = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in context_messages if m.get("content"))
    if progress:
        progress("Planning research...")
    planned = _plan(topic, research_depth, constraints, context)
    sources: list[VerifiedSource] = []
    claims: list[dict] = []
    if progress:
        progress("Searching sources...")
    _retrieve([item.query for item in planned], sources, claims, progress)
    if not sources:
        logger.warning("RIZARTS has no verified web sources; returning a clearly labeled uncited fallback")
        if progress:
            progress("Preparing an uncited best-effort answer...")
        return _unverified_fallback(
            topic,
            context,
            "Web search was unavailable, so current sources and citations could not be verified.",
        )
    if progress:
        progress("Comparing findings...")
        progress("Writing report...")
    synthesis = _synthesize(topic, context, sources, claims)
    if progress:
        progress("Checking gaps...")
    audit = _audit(topic, claims, synthesis)
    refinements = DEPTH_CONFIG[research_depth]["refinements"]
    if audit and audit.status == "REFINE" and refinements:
        if progress:
            progress("Searching sources...")
        old_source_count = len(sources)
        try:
            _retrieve(audit.follow_up_queries[:2], sources, claims, progress)
        except ResearchPipelineError:
            pass
        if len(sources) > old_source_count:
            if progress:
                progress("Comparing findings...")
                progress("Writing report...")
            synthesis = _synthesize(topic, context, sources, claims)
            if progress:
                progress("Checking gaps...")
            _audit(topic, claims, synthesis)
    return synthesis
