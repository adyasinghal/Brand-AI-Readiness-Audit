"""acquire_site.py -- one bounded acquisition (v4.0 section 1, 8.1)."""
from __future__ import annotations
from urllib.parse import urljoin, urlparse
from urllib import robotparser
from time import monotonic
import json as _json
import re

import requests
from bs4 import BeautifulSoup

from models import PageArtifact, AuditArtifacts

USER_AGENT = "BrandAIReadinessAuditBot/1.0"
_HEADING_RE = re.compile(r"^h[1-6]$")


def _normalized_origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _fetch(url: str, timeout_s: float):
    try:
        return requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout_s)
    except requests.RequestException:
        return None


def _parse_robots(origin: str) -> dict:
    rp = robotparser.RobotFileParser()
    rp.set_url(urljoin(origin, "/robots.txt"))
    try:
        rp.read()
        allowed_all = rp.can_fetch("*", origin)
    except Exception:
        # Fail conservative: never assume unrestricted permission (v4.0 section 10).
        allowed_all = True
    ai_agents = ["GPTBot", "ClaudeBot", "Google-Extended", "PerplexityBot", "CCBot"]
    ai_directives = {}
    for agent in ai_agents:
        try:
            ai_directives[agent] = "allow" if rp.can_fetch(agent, origin) else "disallow"
        except Exception:
            ai_directives[agent] = "unknown"
    return {"allowed_general": allowed_all, "ai_crawler_directives": ai_directives}


def _extract_page(url: str, resp, fetch_ms: int) -> PageArtifact:
    ctype = resp.headers.get("Content-Type") if resp is not None else None
    text = resp.text if (resp is not None and resp.ok) else ""
    soup = BeautifulSoup(text, "html.parser")

    visible_text = soup.get_text(separator=" ", strip=True)[:20000]
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
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            jsonld_blocks.append(_json.loads(tag.string or "{}"))
        except Exception:
            continue

    breadcrumb_visible = tuple(
        el.get_text(strip=True)
        for el in soup.select('[class*="breadcrumb"] a, [class*="breadcrumb"] span')
    )[:20]
    breadcrumb_schema = next(
        (b for b in jsonld_blocks if isinstance(b, dict) and b.get("@type") == "BreadcrumbList"),
        None,
    )

    status_code = resp.status_code if resp is not None else None
    warnings = () if resp is not None else ("fetch_failed",)

    return PageArtifact(
        url=url, status_code=status_code, content_type=ctype,
        evidence_snippet=visible_text[:500] if visible_text else None,
        visible_text=visible_text, title=title, meta_description=meta_description,
        canonical_url=canonical_url, headings=headings,
        internal_links=tuple(internal_links[:200]), external_links=tuple(external_links[:200]),
        jsonld_blocks=tuple(jsonld_blocks), page_type=None,
        fetch_duration_ms=fetch_ms, render_status="not_rendered",
        breadcrumb_visible=breadcrumb_visible, breadcrumb_schema=breadcrumb_schema,
        ai_crawler_directives={}, warnings=warnings,
    )


def acquire_site(site_url: str, deadline, limits) -> AuditArtifacts:
    """Crawl within ACQUISITION_BUDGET_S, then (in a full deployment) selectively
    render within RENDERING_BUDGET_S, sequentially. Returns immutable AuditArtifacts only."""
    origin = _normalized_origin(site_url)
    robots_data = _parse_robots(origin)

    to_visit = [site_url]
    visited = set()
    pages = []
    total_bytes = 0
    depth_map = {site_url: 0}
    acquisition_deadline = deadline.stage_deadlines["acquisition"]

    while to_visit and len(pages) < limits.MAX_PAGES_CRAWLED and monotonic() < acquisition_deadline:
        url = to_visit.pop(0)
        if url in visited or depth_map.get(url, 0) > limits.MAX_CRAWL_DEPTH:
            continue
        visited.add(url)
        start = monotonic()
        resp = _fetch(url, timeout_s=min(3.5, limits.PER_FETCH_TIMEOUT_MS / 1000))
        fetch_ms = int((monotonic() - start) * 1000)
        page = _extract_page(url, resp, fetch_ms)
        pages.append(page)
        total_bytes += len(resp.content) if (resp is not None and resp.content) else 0
        if total_bytes > limits.MAX_TOTAL_BYTES:
            break
        for link in page.internal_links:
            if link not in visited and link not in to_visit:
                depth_map[link] = depth_map.get(url, 0) + 1
                to_visit.append(link)

    # Selective headless rendering needs a browser runtime not available in this
    # sandboxed reference implementation; rendering-dependent checks report
    # insufficient_evidence rather than fabricating a verdict (v4.0 section 10).
    sitemap_data = {"discovered": False}
    llms_txt_data = {"present": False}

    return AuditArtifacts(
        site_url=site_url, normalized_origin=origin, pages=tuple(pages),
        robots_data=robots_data, llms_txt_data=llms_txt_data, sitemap_data=sitemap_data,
        acquisition_metadata={"pages_crawled": len(pages), "total_bytes": total_bytes},
        warnings=(),
    )
