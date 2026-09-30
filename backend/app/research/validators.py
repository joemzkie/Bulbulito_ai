import re

from pydantic import BaseModel, ValidationError


MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def parse_strict_json(raw: str, schema: type[BaseModel]) -> BaseModel:
    """Parse strict JSON output; markdown fences and surrounding prose are invalid."""
    import json

    return schema.model_validate(json.loads(raw))


def validate_citations(text: str, verified_urls: set[str] | dict[str, str]) -> list[str]:
    links = [(match.group(1), match.group(2)) for match in MARKDOWN_LINK_RE.finditer(text)]
    allowed = set(verified_urls) if isinstance(verified_urls, dict) else verified_urls
    invalid = [url for _, url in links if url not in allowed]
    if invalid:
        raise ValueError("Synthesis contains URLs outside the verified source whitelist.")
    if isinstance(verified_urls, dict):
        wrong_titles = [(title, url) for title, url in links if title != verified_urls[url]]
        if wrong_titles:
            raise ValueError("Synthesis contains a title that does not match its verified source.")
    return [url for _, url in links]


def validate_planner_count(count: int, min_count: int, max_count: int) -> None:
    if not min_count <= count <= max_count:
        raise ValueError(f"Planner returned {count} queries; expected {min_count}–{max_count} for this depth.")


def validate_claim_sources(claims: list, sources: list) -> None:
    for claim in claims:
        if not claim.claim.strip() or not claim.source_indexes:
            raise ValueError("Every extracted claim must be non-empty and cite evidence.")
        if any(index < 0 or index >= len(sources) for index in claim.source_indexes):
            raise ValueError("An extracted claim references an unknown source index.")


def validate_audit(audit) -> None:
    if audit.status == "COMPLETE" and audit.follow_up_queries:
        raise ValueError("COMPLETE audits must not request follow-up queries.")
    if audit.status == "REFINE" and not 1 <= len(audit.follow_up_queries) <= 2:
        raise ValueError("REFINE audits require one or two follow-up queries.")
