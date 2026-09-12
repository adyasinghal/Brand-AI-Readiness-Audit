"""search_provider.py -- pluggable external search used by freshness-corroboration.

This is the "external_search" optional capability (see capabilities.py). It is
configured via SEARCH_API_URL (and optional SEARCH_API_KEY) env vars pointing at a
search API that returns JSON results for a query. When unset, or when the provider
call fails for any reason (network, auth, rate limit, malformed response), callers
must treat this as an external-search failure and report insufficient_evidence --
never a confirmed absence (v4.0 section 5).
"""
import os
import requests


class SearchProviderError(Exception):
    """Raised for any provider failure -- network, auth, malformed response."""


def is_configured() -> bool:
    return bool(os.environ.get("SEARCH_API_URL"))


def search(query: str, max_results: int, timeout_s: float) -> list:
    """Returns a list of {"title", "url", "snippet"} dicts. Raises SearchProviderError
    on any failure; callers are required to catch it and degrade to
    insufficient_evidence, not propagate a crash or a false "no results"."""
    url = os.environ.get("SEARCH_API_URL")
    if not url:
        raise SearchProviderError("SEARCH_API_URL not configured")
    key = os.environ.get("SEARCH_API_KEY")
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        resp = requests.get(url, params={"q": query, "limit": max_results},
                             headers=headers, timeout=timeout_s)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", data if isinstance(data, list) else [])
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("snippet", "")}
            for r in results[:max_results]
        ]
    except (requests.RequestException, ValueError, AttributeError, KeyError) as exc:
        raise SearchProviderError(str(exc)) from exc
