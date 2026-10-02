import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app
from app.prompts import BAI_CODING_PROMPT
from app.storage import json_storage
from app.research import orchestrator
from app.research import retriever
from app.research.schemas import VerifiedSource
from app.research.validators import validate_citations
from app.providers.registry import MODEL_REGISTRY
from app.research.config import RIZARTS_PROFILE


class AgentApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_root = json_storage.storage.root
        json_storage.storage.root = Path(self.temp.name)
        self.client = TestClient(app)

    def tearDown(self):
        json_storage.storage.root = self.previous_root
        self.temp.cleanup()

    def create_chat(self, agent="jiniral"):
        response = self.client.post("/api/chats", json={"model": "groq-gpt-oss-120b", "agent": agent})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_agent_selection_persists_and_restores(self):
        chat = self.create_chat("bai-coding")
        self.assertEqual(chat["agent"], "bai-coding")
        updated = self.client.patch(f"/api/chats/{chat['id']}", json={"agent": "rizarts"})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["agent"], "rizarts")
        self.assertEqual(self.client.get(f"/api/chats/{chat['id']}").json()["agent"], "rizarts")
        self.assertEqual(self.client.get("/api/chats").json()[0]["agent"], "rizarts")
        stored = json.loads((Path(self.temp.name) / chat["id"] / "conversation.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["agent"], "rizarts")

    def test_normal_agents_use_selected_model_and_agent_prompt_with_history(self):
        chat = self.create_chat()
        with patch("app.services.chat_service.call_chatbot", return_value="answer") as dispatch:
            response = self.client.post(f"/api/chats/{chat['id']}/messages", json={
                "model": "groq-gpt-oss-120b", "agent": "bai-coding", "content": "Why KeyError?",
            })
        self.assertEqual(response.status_code, 200, response.text)
        selected_model, messages = dispatch.call_args.args
        self.assertEqual(selected_model, "groq-gpt-oss-120b")
        self.assertEqual(messages[0]["content"], BAI_CODING_PROMPT)
        self.assertEqual(messages[-1], {"role": "user", "content": "Why KeyError?"})
        self.assertEqual(response.json()["conversation"]["agent"], "bai-coding")
        with patch("app.services.chat_service.call_chatbot", return_value="general answer") as dispatch:
            general = self.client.post(f"/api/chats/{chat['id']}/messages", json={
                "model": "groq-gpt-oss-120b", "agent": "jiniral", "content": "What is a PostgreSQL index?",
            })
        self.assertEqual(general.status_code, 200)
        general_messages = dispatch.call_args.args[1]
        self.assertIn("You are JINIRAL", general_messages[0]["content"])
        self.assertTrue(any(message["content"] == "Why KeyError?" for message in general_messages))
        self.assertEqual(general.json()["conversation"]["agent"], "jiniral")

    def test_bai_coding_prompt_covers_reasoning_and_capability_boundaries(self):
        for required_guidance in (
            "not an autonomous coding agent",
            "must not edit, create, or delete files",
            "execute terminal commands",
            "only receive the conversation and the code or context the user provides",
            "Never claim to have inspected files",
            "Never claim to have run or tested code",
            "Keep this reasoning private",
            "Separate what the code shows from possibilities that depend on missing context",
            "smallest correct fix",
            "Do not rewrite unrelated code",
        ):
            with self.subTest(guidance=required_guidance):
                self.assertIn(required_guidance, BAI_CODING_PROMPT)

    def test_invalid_agent_is_rejected(self):
        chat = self.create_chat()
        response = self.client.post(f"/api/chats/{chat['id']}/messages", json={
            "model": "groq-gpt-oss-120b", "agent": "thinking", "content": "Hello",
        })
        self.assertEqual(response.status_code, 422)

    def test_rizarts_streams_progress_and_persists_the_report(self):
        chat = self.create_chat()

        def fake_research(**kwargs):
            kwargs["progress"]("Planning research...")
            kwargs["progress"]("Searching sources...")
            return "# Executive Takeaway\nVerified report"

        with patch("app.services.chat_service.run_rizarts_research", side_effect=fake_research):
            response = self.client.post(f"/api/chats/{chat['id']}/messages", json={
                "model": "groq-gpt-oss-120b", "agent": "rizarts", "content": "Research PostgreSQL partitioning",
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertIn("Planning research...", response.text)
        self.assertIn('event: complete', response.text)
        stored = self.client.get(f"/api/chats/{chat['id']}").json()
        self.assertEqual(stored["agent"], "rizarts")
        self.assertEqual(stored["messages"][-1]["content"], "# Executive Takeaway\nVerified report")


class RizartsPipelineTests(unittest.TestCase):
    def test_rizarts_profile_models_are_registry_entries(self):
        self.assertTrue(all(key in MODEL_REGISTRY for key in RIZARTS_PROFILE.values()))
        self.assertEqual(set(RIZARTS_PROFILE.values()), {"gemini-3.5-flash-lite"})

    def test_duckduckgo_results_are_injected_as_source_bound_snippets(self):
        results = [
            {"title": "Source one", "href": "https://example.test/one", "body": "First result snippet."},
            {"title": "Source two", "href": "https://example.test/two", "body": "Second result snippet."},
            {"title": "Invalid URL", "href": "javascript:alert(1)", "body": "Must be ignored."},
        ]
        with patch("app.research.retriever.DDGS") as ddgs_class:
            ddgs_class.return_value.text.return_value = results
            context, sources = retriever.search_web("planned query")
        ddgs_class.return_value.text.assert_called_once_with("planned query", max_results=5, backend="duckduckgo")
        self.assertIn("First result snippet.", context)
        self.assertIn("Second result snippet.", context)
        self.assertEqual([source.url for source in sources], ["https://example.test/one", "https://example.test/two"])
        self.assertEqual(sources[0].content, "First result snippet.")
        self.assertEqual(sources[0].search_queries, ["planned query"])

    def test_duckduckgo_failure_is_sanitized(self):
        private_detail = "private proxy details"
        with patch("app.research.retriever.DDGS") as ddgs_class:
            ddgs_class.return_value.text.side_effect = RuntimeError(private_detail)
            with self.assertRaises(retriever.WebRetrievalError) as raised:
                retriever.search_web("planned query")
        self.assertEqual(raised.exception.category, "search_unavailable")
        self.assertNotIn(private_detail, str(raised.exception))

    def test_retrieval_failure_does_not_abort_other_planned_queries(self):
        planner = json.dumps({"queries": [
            {"query": f"specific query {index}", "purpose": purpose}
            for index, purpose in enumerate(("background", "technical", "metrics"))
        ]})
        source = VerifiedSource(title="Search result", url="https://example.test/page", query="specific query 1", content="result snippet")
        with patch.object(orchestrator, "call_chatbot", return_value=planner), \
             patch.object(orchestrator, "search_web", side_effect=[
                 retriever.WebRetrievalError("search_unavailable", "temporarily unavailable"),
                 ("Search result snippet", [source]),
                 ("No results", []),
             ]) as search, \
             patch.object(orchestrator, "_extract", return_value=[]), \
             patch.object(orchestrator, "_synthesize", return_value="validated report"), \
             patch.object(orchestrator, "_audit", return_value=None):
            result = orchestrator.run_rizarts_research("topic", research_depth="quick")
        self.assertEqual(result, "validated report")
        self.assertEqual(search.call_count, 3)

    def test_planner_search_claims_report_and_audit_pipeline(self):
        planner = json.dumps({"queries": [
            {"query": f"postgresql partitioning evidence {index}", "purpose": purpose}
            for index, purpose in enumerate(("background", "technical", "metrics"))
        ]})
        claim = json.dumps({"claims": [{
            "claim": "Partition pruning can remove irrelevant partitions.",
            "source_indexes": [0], "confidence": "high", "evidence_type": "documentation",
        }]})
        source = VerifiedSource(title="PostgreSQL Docs", url="https://www.postgresql.org/docs/current/ddl-partitioning.html", query="q", content="pruning")
        report = "# Executive Takeaway\nSummary [PostgreSQL Docs](https://www.postgresql.org/docs/current/ddl-partitioning.html)\n# Core Technical Analysis\nDetails\n# Current Bottlenecks / Controversies\nLimits\n# Conclusion\nDone\n## Sources\n- [PostgreSQL Docs](https://www.postgresql.org/docs/current/ddl-partitioning.html)"
        audit = json.dumps({"status": "COMPLETE", "gaps": [], "follow_up_queries": []})
        with patch.object(orchestrator, "call_chatbot", side_effect=[planner, claim, claim, claim, report, audit]), patch.object(orchestrator, "search_web", return_value=("search snippets", [source])):
            result = orchestrator.run_rizarts_research("PostgreSQL partitioning", research_depth="quick")
        self.assertEqual(result, report)

    def test_unverified_citation_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_citations("[Made up](https://example.invalid/source)", {"https://verified.test/source"})

    def test_verified_url_cannot_be_relabelled_with_a_fake_title(self):
        with self.assertRaises(ValueError):
            validate_citations("[Fake title](https://verified.test/source)", {"https://verified.test/source": "Verified title"})

    def test_refinement_runs_at_most_once(self):
        planner = json.dumps({"queries": [
            {"query": f"topic query {index}", "purpose": purpose}
            for index, purpose in enumerate(("background", "technical", "metrics"))
        ]})
        claim = json.dumps({"claims": [{
            "claim": "Evidence-backed finding.", "source_indexes": [0],
            "confidence": "medium", "evidence_type": "study",
        }]})
        audits = [
            json.dumps({"status": "REFINE", "gaps": ["Need more current evidence."], "follow_up_queries": ["topic field evidence 2026"]}),
            json.dumps({"status": "REFINE", "gaps": ["One gap remains."], "follow_up_queries": ["another query"]}),
        ]
        sources = [(f"grounded {index}", [VerifiedSource(
            title=f"Verified {index}", url=f"https://verified.test/{index}", query=f"query {index}", content="evidence",
        )]) for index in range(4)]
        with patch.object(orchestrator, "call_chatbot", side_effect=[planner, claim, claim, claim, *audits[0:1], claim, audits[1]]), \
             patch.object(orchestrator, "search_web", side_effect=sources) as search, \
             patch.object(orchestrator, "_synthesize", side_effect=["validated draft one", "validated draft two"]) as synthesize:
            result = orchestrator.run_rizarts_research("Topic", research_depth="standard")
        self.assertEqual(result, "validated draft two")
        self.assertEqual(search.call_count, 4)
        self.assertEqual(synthesize.call_count, 2)

    def test_no_search_sources_fails_safely_without_synthesis(self):
        planner = json.dumps({"queries": [
            {"query": f"specific query {index}", "purpose": purpose}
            for index, purpose in enumerate(("background", "technical", "metrics"))
        ]})
        with patch.object(orchestrator, "call_chatbot", return_value=planner), patch.object(orchestrator, "search_web", return_value=("No live results found.", [])):
            with self.assertRaises(orchestrator.ResearchPipelineError):
                orchestrator.run_rizarts_research("topic", research_depth="quick")


if __name__ == "__main__":
    unittest.main()
