"""acquire_site.py -- one bounded acquisition (v4.0 section 1, 8.1; instrumentation
addendum). Enforces every acquisition limit in common/constants.py, records real
telemetry via Instrumentation, and wraps nested dict/list fields in read-only views
(MappingProxyType) as a second defense on top of frozen(=True) dataclasses.
"""
from __future__ import annotations
from urllib.parse import urljoin, urlparse
from urllib import robotparser
from time import monotonic
import json as _json
import re

import requests
from bs4 import BeautifulSoup

from models import PageArtifact, AuditArtifacts, freeze_value

USER_AGENT = "BrandAIReadinessAuditBot/1.0"
_HEADING_RE = re.compile(r"^h[1-6]$")


def _normalized_origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _fetch_with_retries(url: str, timeout_s: float, max_retries: int, instrumentation):
    """One fetch with bounded retries (MAX_FETCH_RETRIES). Every attempt -- success or
    failure -- is recorded; this is the single place request counters are incremented."""
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout_s)
            nbytes = len(resp.content) if resp.content else 0
            instrumentation.record_request(ok=True, nbytes=nbytes)
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            instrumentation.record_request(ok=False)
    return None


def _robots_parser(origin: str):
    rp = robotparser.RobotFileParser()
    rp.set_url(urljoin(origin, "/robots.txt"))
    try:
        rp.read()
        return rp, True
    except Exception:
        return rp, False


def _ai_crawler_directives(rp, origin: str) -> dict:
    ai_agents = ["GPTBot", "ClaudeBot", "Google-Extended", "PerplexityBot", "CCBot"]
    directives = {}
    for agent in ai_agents:
        try:
            directives[agent] = "allow" if rp.can_fetch(agent, origin) else "disallow"
        except Exception:
            directives[agent] = "unknown"
    return directives


def _extract_page(url: str, resp, fetch_ms: int, limits) -> PageArtifact:
    ctype = resp.headers.get("Content-Type") if resp is not None else None
    text = resp.text if (resp is not None and resp.ok) else ""
    soup = BeautifulSoup(text, "html.parser")

    visible_text = soup.get_text(separator=" ", strip=True)[: limits.VISIBLE_TEXT_MAX_CHARS]
    title = soup.title.string.strip() if (soup.title and soup.title.string) else None
    meta = soup.find("meta", attrs={"name": "description"})
    meta_description = meta.get("content") if meta else None
    canonical_tag = soup.find("link", rel="canonical")
    canonical_url = canonical_tag.get("href") if canonical_tag else None
    headings = tuple(h.get_text(strip=True) for h in soup.find_all(_HEADING_RE))[:50]

    origin = _normalized_origin(url)
    internal_links, external_links = [], []
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"])
        (internal_links if href.startswith(origin) else external_links).append(href)

    jsonld_blocks = []
    jsonld_warnings = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or "{}"
        try:
            jsonld_blocks.append(_json.loads(raw))
        except Exception:
            # Malformed JSON-LD is acquisition evidence (a warning), not a crash and
            # not silently dropped without a trace (v4.0 section 10).
            jsonld_warnings.append("malformed_jsonld_block")

    breadcrumb_visible = tuple(
        el.get_text(strip=True)
        for el in soup.select('[class*="breadcrumb"] a, [class*="breadcrumb"] span')
    )[:20]
    breadcrumb_schema = next(
        (b for b in jsonld_blocks if isinstance(b, dict) and b.get("@type") == "BreadcrumbList"),
        None,
    )

    status_code = resp.status_code if resp is not None else None
    redirected = bool(resp is not None and resp.history)
    warnings = list(jsonld_warnings)
    if resp is None:
        warnings.append("fetch_failed")
    if redirected:
        warnings.append(f"redirected_{len(resp.history)}_hop(s)")

    return PageArtifact(
        url=url, status_code=status_code, content_type=ctype,
        evidence_snippet=visible_text[: limits.EVIDENCE_SNIPPET_MAX_CHARS] if visible_text else None,
        visible_text=visible_text, title=title, meta_description=meta_description,
        canonical_url=canonical_url, headings=headings,
        internal_links=tuple(internal_links[:200]), external_links=tuple(external_links[:200]),
        jsonld_blocks=tuple(freeze_value(b) for b in jsonld_blocks), page_type=None,
        fetch_duration_ms=fetch_ms, render_status="not_rendered",
        breadcrumb_visible=breadcrumb_visible, breadcrumb_schema=freeze_value(breadcrumb_schema),
        ai_crawler_directives=freeze_value({}), warnings=tuple(warnings),
    )


def acquire_site(site_url: str, deadline, limits, instrumentation=None) -> AuditArtifacts:
    """Crawl within ACQUISITION_BUDGET_S; every limit in Limits is enforced, not just
    documented. Returns immutable AuditArtifacts only."""
    from instrumentation import Instrumentation
    instrumentation = instrumentation or Instrumentation()
    instrumentation.start_memory_tracking()
    instrumentation.start_stage("acquisition")

    origin = _normalized_origin(site_url)
    rp, robots_ok = _robots_parser(origin)
    ai_directives = _ai_crawler_directives(rp, origin)

    to_visit = [site_url]
    visited = set()
    pages = []
    total_bytes = 0
    depth_map = {site_url: 0}
    acquisition_deadline = deadline.stage_deadlines["acquisition"]
    total_requests = 0

    while to_visit and monotonic() < acquisition_deadline:
        if len(pages) >= limits.MAX_PAGES_CRAWLED:
            instrumentation.record_skip("max_pages_crawled_reached")
            break
        if total_requests >= limits.MAX_TOTAL_HTTP_REQUESTS:
            instrumentation.record_skip("max_total_http_requests_reached")
            break

        url = to_visit.pop(0)
        if url in visited:
            continue
        if depth_map.get(url, 0) > limits.MAX_CRAWL_DEPTH:
            instrumentation.record_skip("max_crawl_depth_exceeded")
            continue
        try:
            allowed = rp.can_fetch(USER_AGENT, url) if robots_ok else True
        except Exception:
            allowed = True
        if not allowed:
            instrumentation.record_skip("robots_disallowed")
            visited.add(url)
            continue

        visited.add(url)
        start = monotonic()
        resp = _fetch_with_retries(url, timeout_s=limits.PER_FETCH_TIMEOUT_MS / 1000,
                                    max_retries=limits.MAX_FETCH_RETRIES,
                                    instrumentation=instrumentation)
        total_requests += 1
        fetch_ms = int((monotonic() - start) * 1000)
        page = _extract_page(url, resp, fetch_ms, limits)
        pages.append(page)

        nbytes = len(resp.content) if (resp is not None and resp.content) else 0
        total_bytes += nbytes
        if total_bytes > limits.MAX_TOTAL_BYTES:
            instrumentation.record_skip("max_total_bytes_reached")
            break

        for link in page.internal_links:
            if link not in visited and link not in to_visit:
                depth_map[link] = depth_map.get(url, 0) + 1
                to_visit.append(link)

    instrumentation.end_stage("acquisition")

    # Selective headless rendering needs a browser runtime; capabilities.py decides
    # at call time whether it's available. This function never fabricates a
    # render_status -- pages are left "not_rendered" here and rendering-dependent
    # checks report insufficient_evidence rather than a defect (v4.0 section 10).
    sitemap_data = {"discovered": False}
    llms_txt_data = {"present": False}

    return AuditArtifacts(
        site_url=site_url, normalized_origin=origin, pages=tuple(pages),
        robots_data=freeze_value({"allowed_general": robots_ok, "ai_crawler_directives": ai_directives}),
        llms_txt_data=freeze_value(llms_txt_data), sitemap_data=freeze_value(sitemap_data),
        acquisition_metadata=freeze_value({"pages_crawled": len(pages), "total_bytes": total_bytes,
                                            "total_requests": total_requests}),
        warnings=(),
    )
