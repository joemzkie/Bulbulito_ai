"""DuckDuckGo-backed web retrieval for RIZARTS."""

import logging
from urllib.parse import urlsplit

from ddgs import DDGS

from .schemas import VerifiedSource

logger = logging.getLogger("bulbulito.research")


class WebRetrievalError(Exception):
    """Safe failure raised when the external text-search backend is unavailable."""

    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)


def search_web(query: str, max_results: int = 5) -> tuple[str, list[VerifiedSource]]:
    """Fetch DuckDuckGo text snippets; no Gemini Search Grounding is used."""
    try:
        results = DDGS().text(query, max_results=max_results, backend="duckduckgo")
    except Exception as exc:
        # Do not log exception text from an external request.
        logger.warning("RIZARTS web retrieval failed: category=search_unavailable error_type=%s", type(exc).__name__)
        raise WebRetrievalError(
            "search_unavailable",
            "DuckDuckGo web search is temporarily unavailable. Please try again.",
        ) from exc

    sources: list[VerifiedSource] = []
    formatted_snippets: list[str] = []
    seen_urls: set[str] = set()
    for item in results or []:
        title = str(item.get("title") or "Untitled").strip()
        url = str(item.get("href") or "").strip()
        snippet = str(item.get("body") or "").strip()
        parsed_url = urlsplit(url)
        if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc or url in seen_urls:
            continue
        seen_urls.add(url)
        sources.append(VerifiedSource(
            title=title,
            url=url,
            query=query,
            search_queries=[query],
            content=snippet,
        ))
        formatted_snippets.append(
            f"- Title: {title}\n  URL: {url}\n  Snippet: {snippet or 'No snippet was provided.'}"
        )

    context = "\n\n".join(formatted_snippets) if formatted_snippets else "No live results found."
    return context, sources
