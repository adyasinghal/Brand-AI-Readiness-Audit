"""acquire_site.py -- one bounded acquisition (v4.0 section 1, 8.1; instrumentation
addendum). Enforces every acquisition limit in common/constants.py, records real
telemetry via Instrumentation, and wraps nested dict/list fields in read-only views
(MappingProxyType) as a second defense on top of frozen(=True) dataclasses.

Safety (Round-3 handout, Priority 1): every URL this module is about to fetch --
the initial target, robots.txt, sitemap.xml, llms.txt, and every discovered link --
is passed through url_safety.classify_url() first. Blocked URLs are recorded as
safety skips (instrumentation.record_safety_block), never surfaced as findings.
Robots.txt retrieval/parse failures never fail open: absence (404) is the only
state that means "allowed"; every other failure mode (timeout, other HTTP error,
undecodable body) makes the crawl conservative -- only the single initial page is
fetched, no links are followed -- and the failure mode is recorded in
robots_data["status"] for downstream skills to see. Only GET requests are ever
issued against the target site; nothing here can submit a form, authenticate, or
otherwise mutate the site.
"""
from __future__ import annotations
from urllib.parse import urljoin, urlparse
from urllib import robotparser
from xml.etree import ElementTree
from time import monotonic
import json as _json
import re

import requests
from bs4 import BeautifulSoup

from models import PageArtifact, AuditArtifacts, freeze_value
from url_safety import classify_url, same_origin

USER_AGENT = "BrandAIReadinessAuditBot/1.0"
_HEADING_RE = re.compile(r"^h[1-6]$")
_MAX_REDIRECT_HOPS = 5


def _normalized_origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _noop_instrumentation():
    from instrumentation import Instrumentation
    return Instrumentation()


def _safe_get(url: str, timeout_s: float, allow_private: bool, instrumentation,
              max_response_bytes: int, redirects_remaining: int = _MAX_REDIRECT_HOPS,
              origin: str = None, hops_followed: int = 0):
    """A single safety-checked, byte-bounded, streaming GET. Redirects are followed
    manually (allow_redirects=False) so every hop is re-validated for SSRF and
    checked against same-origin policy before being followed -- requests' own
    allow_redirects=True would happily follow a redirect straight into a private
    address after the first hop passed validation.

    Returns (_BoundedResponse | None, final_status: str) where final_status is one
    of "ok", "blocked", "failed", "cross_origin_redirect_blocked", "too_many_redirects".
    """
    check = classify_url(url, allow_private=allow_private)
    if not check.safe:
        instrumentation.record_safety_block(url, check.reason)
        return None, "blocked"

    try:
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=timeout_s,
            stream=True, allow_redirects=False,
        )
    except requests.Timeout:
        instrumentation.record_request(ok=False, timed_out=True)
        return None, "timeout"
    except requests.RequestException:
        instrumentation.record_request(ok=False)
        return None, "failed"

    if 300 <= resp.status_code < 400:
        location = resp.headers.get("Location")
        resp.close()
        instrumentation.record_request(ok=True, nbytes=0)
        instrumentation.record_redirect()
        if not location:
            return None, "failed"
        target = urljoin(url, location)
        if origin is not None and not same_origin(target, origin):
            return _BoundedResponse.from_redirect(resp.status_code, target), "cross_origin_redirect_blocked"
        if redirects_remaining <= 0:
            return None, "too_many_redirects"
        return _safe_get(target, timeout_s, allow_private, instrumentation, max_response_bytes,
                          redirects_remaining - 1, origin, hops_followed + 1)

    # Stream and enforce the byte budget DURING download, not after a full read.
    chunks = []
    total = 0
    truncated = False
    try:
        for chunk in resp.iter_content(chunk_size=8192):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_response_bytes:
                truncated = True
                instrumentation.record_truncated()
                break
            chunks.append(chunk)
    except requests.Timeout:
        resp.close()
        instrumentation.record_request(ok=False, timed_out=True)
        return None, "timeout"
    except requests.RequestException:
        resp.close()
        instrumentation.record_request(ok=False)
        return None, "failed"
    finally:
        resp.close()

    content = b"".join(chunks)
    instrumentation.record_request(ok=True, nbytes=len(content))
    return _BoundedResponse(resp, content, truncated, redirect_hops=hops_followed), "ok"


class _BoundedResponse:
    def __init__(self, resp, content, truncated, redirect_hops=0):
        self.status_code = resp.status_code
        self.headers = resp.headers
        self.history = list(resp.history)
        self.redirect_hops = redirect_hops
        self.content = content
        self.truncated = truncated
        enc = resp.encoding or "utf-8"
        try:
            self.text = content.decode(enc, errors="replace")
        except LookupError:
            self.text = content.decode("utf-8", errors="replace")

    @property
    def ok(self):
        return self.status_code is not None and 200 <= self.status_code < 400

    @classmethod
    def from_redirect(cls, status_code, location):
        obj = cls.__new__(cls)
        obj.status_code = status_code
        obj.headers = {}
        obj.history = []
        obj.redirect_hops = 0
        obj.content = b""
        obj.truncated = False
        obj.text = ""
        obj._blocked_redirect_target = location
        return obj


def _fetch_with_retries(url: str, timeout_s: float, max_retries: int, instrumentation,
                         allow_private: bool, max_response_bytes: int, origin: str):
    last_status = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            instrumentation.record_retry()
        resp, status = _safe_get(url, timeout_s, allow_private, instrumentation,
                                  max_response_bytes, origin=origin)
        last_status = status
        if status == "ok":
            return resp, status
        if status in ("blocked", "cross_origin_redirect_blocked"):
            return resp, status  # no point retrying a policy decision
    return None, last_status


def _fetch_robots(origin: str, timeout_s: float, allow_private: bool, instrumentation):
    """Returns (robots_text_or_None, status) where status is one of:
    "ok", "absent" (404 -> allow-all per convention), "inaccessible" (other HTTP
    error or connection failure), "timeout", "malformed" (fetched but undecodable),
    "blocked" (the robots URL itself failed the SSRF check)."""
    url = urljoin(origin, "/robots.txt")
    check = classify_url(url, allow_private=allow_private)
    if not check.safe:
        instrumentation.record_safety_block(url, check.reason)
        return None, "blocked"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout_s)
        instrumentation.record_request(ok=True, nbytes=len(resp.content or b""))
    except requests.Timeout:
        instrumentation.record_request(ok=False)
        return None, "timeout"
    except requests.RequestException:
        instrumentation.record_request(ok=False)
        return None, "inaccessible"

    if resp.status_code == 404:
        return "", "absent"
    if resp.status_code >= 400:
        return None, "inaccessible"
    # robots.txt is specified as UTF-8/ASCII; decode strictly as UTF-8 regardless
    # of what requests' charset auto-detection guesses (it defaults undeclared
    # text/* bodies to Latin-1, which never raises and would hide real corruption).
    try:
        text = resp.content.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None, "malformed"
    return text, "ok"


def _robots_policy(origin: str, timeout_s: float, allow_private: bool, instrumentation):
    """NEVER fails open. "absent" (confirmed 404) is the only failure-adjacent state
    that means allow-all, because that is the documented meaning of no robots.txt.
    Every other non-"ok" state (timeout, inaccessible, malformed, blocked) makes the
    parser deny everything -- callers must then crawl conservatively (v4.0 section
    10: "Crawl conservatively; never assume unrestricted permission")."""
    text, status = _fetch_robots(origin, timeout_s, allow_private, instrumentation)
    rp = robotparser.RobotFileParser()
    if status == "absent":
        rp.parse("".splitlines())
        return rp, status, False
    if status == "ok":
        rp.parse(text.splitlines())
        return rp, status, False
    rp.parse("User-agent: *\nDisallow: /\n".splitlines())
    return rp, status, True


def _ai_crawler_directives(rp, origin: str, conservative: bool) -> dict:
    if conservative:
        return {}
    ai_agents = ["GPTBot", "ClaudeBot", "Google-Extended", "PerplexityBot", "CCBot"]
    directives = {}
    for agent in ai_agents:
        try:
            directives[agent] = "allow" if rp.can_fetch(agent, origin) else "disallow"
        except Exception:
            directives[agent] = "unknown"
    return directives


def _fetch_sitemap(origin: str, timeout_s: float, allow_private: bool, instrumentation,
                    max_urls: int = 200) -> dict:
    """Actually fetches /sitemap.xml (bounded). Distinguishes present/absent/
    inaccessible/malformed -- never silently claims "not discovered" without having
    looked."""
    url = urljoin(origin, "/sitemap.xml")
    check = classify_url(url, allow_private=allow_private)
    if not check.safe:
        instrumentation.record_safety_block(url, check.reason)
        return {"discovered": False, "status": "blocked", "urls": []}
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout_s)
        instrumentation.record_request(ok=True, nbytes=len(resp.content or b""))
    except requests.RequestException:
        instrumentation.record_request(ok=False)
        return {"discovered": False, "status": "inaccessible", "urls": []}
    if resp.status_code == 404:
        return {"discovered": False, "status": "absent", "urls": []}
    if resp.status_code >= 400:
        return {"discovered": False, "status": "inaccessible", "urls": []}
    try:
        root = ElementTree.fromstring(resp.content)
    except ElementTree.ParseError:
        return {"discovered": False, "status": "malformed", "urls": []}
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [el.text.strip() for el in root.findall(".//sm:url/sm:loc", ns) if el.text]
    if not locs:
        locs = [el.text.strip() for el in root.findall(".//loc") if el.text]
    return {"discovered": True, "status": "ok", "urls": locs[:max_urls]}


def _fetch_llms_txt(origin: str, timeout_s: float, allow_private: bool, instrumentation) -> dict:
    url = urljoin(origin, "/llms.txt")
    check = classify_url(url, allow_private=allow_private)
    if not check.safe:
        instrumentation.record_safety_block(url, check.reason)
        return {"present": False, "status": "blocked"}
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout_s)
        instrumentation.record_request(ok=True, nbytes=len(resp.content or b""))
    except requests.RequestException:
        instrumentation.record_request(ok=False)
        return {"present": False, "status": "inaccessible"}
    if resp.status_code == 404:
        return {"present": False, "status": "absent"}
    if resp.status_code >= 400:
        return {"present": False, "status": "inaccessible"}
    return {"present": True, "status": "ok"}


_PRODUCT_PATH_RE = re.compile(r"/(product|products|item|items|shop|store|sku)(/|$)", re.I)
_ARTICLE_PATH_RE = re.compile(r"/(blog|news|article|articles|press|insights|stories)(/|$)", re.I)
_CONTACT_PATH_RE = re.compile(r"/(contact|contact-us|get-in-touch)(/|$)", re.I)
_ABOUT_PATH_RE = re.compile(r"/(about|about-us|company|team|who-we-are)(/|$)", re.I)
_LEGAL_PATH_RE = re.compile(r"/(privacy|terms|legal|cookie|tos)(/|-|$)", re.I)
_CATEGORY_PATH_RE = re.compile(r"/(category|categories|collection|collections|catalog)(/|$)", re.I)

# Page-type classification is an acquisition-owned observation (v4.0 section 2 lists
# "page type" among the acquisition-owned fields): it is derived only from facts
# already captured during acquisition -- URL path shape and JSON-LD @type -- never
# from a later analysis conclusion. It downstream lets structured-data checks,
# rendering thresholds, and freshness-category calibration compare pages against a
# type-appropriate expectation instead of one flat rule for every page.
def _classify_page_type(url: str, origin: str, jsonld_blocks, path: str) -> str:
    jsonld_types = {b.get("@type") for b in jsonld_blocks
                    if isinstance(b, dict) and isinstance(b.get("@type"), str)}
    if url.rstrip("/") == origin.rstrip("/") or (path or "") in ("", "/"):
        return "home"
    if jsonld_types & {"Product", "Offer", "IndividualProduct"}:
        return "product"
    if jsonld_types & {"Article", "BlogPosting", "NewsArticle"}:
        return "article"
    if jsonld_types & {"ContactPage"}:
        return "contact"
    if jsonld_types & {"AboutPage"}:
        return "about"
    if _PRODUCT_PATH_RE.search(path):
        return "product"
    if _ARTICLE_PATH_RE.search(path):
        return "article"
    if _CONTACT_PATH_RE.search(path):
        return "contact"
    if _ABOUT_PATH_RE.search(path):
        return "about"
    if _LEGAL_PATH_RE.search(path):
        return "legal"
    if _CATEGORY_PATH_RE.search(path):
        return "category"
    return "other"


def _extract_page(url: str, resp, fetch_ms: int, limits, fetch_status: str = "ok") -> PageArtifact:
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
    redirect_hops = getattr(resp, "redirect_hops", 0) if resp is not None else 0
    warnings = list(jsonld_warnings)
    if resp is None:
        # Distinguish *why* nothing was fetched -- "timed out" vs. "connection/other
        # failure" vs. "too many redirects" are different facts, not one bucket
        # (Round-3 handout: "report budget exhaustion separately [from] fetch
        # failure", generalized here to every failure mode being named honestly).
        warnings.append(f"fetch_{fetch_status}")
    if redirect_hops:
        warnings.append(f"redirected_{redirect_hops}_hop(s)")
    if resp is not None and getattr(resp, "truncated", False):
        warnings.append("response_truncated_at_byte_budget")

    return PageArtifact(
        url=url, status_code=status_code, content_type=ctype,
        evidence_snippet=visible_text[: limits.EVIDENCE_SNIPPET_MAX_CHARS] if visible_text else None,
        visible_text=visible_text, title=title, meta_description=meta_description,
        canonical_url=canonical_url, headings=headings,
        internal_links=tuple(internal_links[:200]), external_links=tuple(external_links[:200]),
        jsonld_blocks=tuple(freeze_value(b) for b in jsonld_blocks),
        page_type=_classify_page_type(url, origin, jsonld_blocks, urlparse(url).path),
        fetch_duration_ms=fetch_ms, render_status="not_rendered",
        breadcrumb_visible=breadcrumb_visible, breadcrumb_schema=freeze_value(breadcrumb_schema),
        ai_crawler_directives=freeze_value({}), warnings=tuple(warnings),
    )


def acquire_site(site_url: str, deadline, limits, instrumentation=None,
                  allow_private_targets: bool = False) -> AuditArtifacts:
    """Crawl within ACQUISITION_BUDGET_S; every limit in Limits is enforced, not just
    documented. Returns immutable AuditArtifacts only.

    allow_private_targets defaults to False (safe): production callers never set
    it. Test fixtures running a local ThreadingHTTPServer on 127.0.0.1 pass True
    explicitly -- see tests/fixtures_server.py callers.
    """
    instrumentation = instrumentation or _noop_instrumentation()
    instrumentation.start_memory_tracking()
    instrumentation.start_stage("acquisition")

    origin = _normalized_origin(site_url)
    top_warnings = []

    initial_check = classify_url(site_url, allow_private=allow_private_targets)
    if not initial_check.safe:
        instrumentation.record_safety_block(site_url, initial_check.reason)
        instrumentation.end_stage("acquisition")
        return AuditArtifacts(
            site_url=site_url, normalized_origin=origin, pages=(),
            robots_data=freeze_value({"allowed_general": False, "status": "not_checked",
                                       "ai_crawler_directives": {}}),
            llms_txt_data=freeze_value({"present": False, "status": "not_checked"}),
            sitemap_data=freeze_value({"discovered": False, "status": "not_checked", "urls": []}),
            acquisition_metadata=freeze_value({"pages_crawled": 0, "total_bytes": 0, "total_requests": 0}),
            warnings=(f"initial_url_blocked:{initial_check.reason}",),
        )

    per_fetch_timeout_s = limits.PER_FETCH_TIMEOUT_MS / 1000
    rp, robots_status, conservative = _robots_policy(
        origin, per_fetch_timeout_s, allow_private_targets, instrumentation)
    ai_directives = _ai_crawler_directives(rp, origin, conservative)
    if conservative:
        top_warnings.append(f"robots_txt_{robots_status}_conservative_crawl")
    # general_disallow is only ever a concrete True/False when robots.txt was
    # actually retrieved and parsed (status == "ok"/"absent"); when retrieval or
    # parsing failed it stays None ("we could not check"), never inferred as a
    # confirmed disallow -- analyze_crawlability.py must treat None as insufficient
    # evidence, not a defect (v4.0 section 10, Invariant I-1).
    general_disallow = (not rp.can_fetch(USER_AGENT, origin)) if not conservative else None

    sitemap_data = _fetch_sitemap(origin, per_fetch_timeout_s, allow_private_targets, instrumentation)
    llms_txt_data = _fetch_llms_txt(origin, per_fetch_timeout_s, allow_private_targets, instrumentation)

    to_visit = [site_url]
    visited = set()
    discovered = {site_url}
    pages = []
    total_bytes = 0
    depth_map = {site_url: 0}
    acquisition_deadline = deadline.stage_deadlines["acquisition"]
    total_requests = 0

    # sitemap.xml URLs are "discovered" the moment the sitemap is read, whether or
    # not the crawl ever reaches them -- discovered is a superset of fetched.
    discovered.update(sitemap_data.get("urls", []))
    # Sitemap is also queued for crawling, not just counted (v4.0 section 8.1:
    # "discover sitemap and fall back to internal links") -- a page listed only in
    # the sitemap and never linked from anywhere else on the site (a genuine
    # broken-navigation / isolated-page case) would otherwise never be fetched at
    # all. Seeded at depth 1 (one hop from the root) and still subject to every
    # existing bound below (max_pages, MAX_CRAWL_DEPTH, deadline, dedup).
    for _sitemap_url in sitemap_data.get("urls", []):
        if _sitemap_url not in visited and _sitemap_url not in to_visit:
            to_visit.append(_sitemap_url)
            depth_map.setdefault(_sitemap_url, 1)

    # Conservative mode (robots retrieval/parse failed): fetch only the single
    # initial page and follow no links, rather than assuming unrestricted access.
    max_pages = 1 if conservative else limits.MAX_PAGES_CRAWLED

    while to_visit and monotonic() < acquisition_deadline:
        if len(pages) >= max_pages:
            instrumentation.record_skip("max_pages_crawled_reached" if not conservative
                                         else "conservative_mode_single_page_only")
            break
        if total_requests >= limits.MAX_TOTAL_HTTP_REQUESTS:
            instrumentation.record_skip("max_total_http_requests_reached")
            break

        url = to_visit.pop(0)
        if url in visited:
            instrumentation.record_deduplicated()
            continue
        if depth_map.get(url, 0) > limits.MAX_CRAWL_DEPTH:
            instrumentation.record_skip("max_crawl_depth_exceeded")
            continue

        try:
            allowed = rp.can_fetch(USER_AGENT, url)
        except Exception:
            allowed = False  # never fail open on a parse-time error either
        if not allowed:
            instrumentation.record_skip("robots_disallowed")
            visited.add(url)
            continue

        visited.add(url)
        remaining_budget = max(0, limits.MAX_TOTAL_BYTES - total_bytes)
        timeout_s = min(per_fetch_timeout_s, max(0.5, deadline.remaining_seconds()))
        start = monotonic()
        resp, status = _fetch_with_retries(
            url, timeout_s=timeout_s, max_retries=limits.MAX_FETCH_RETRIES,
            instrumentation=instrumentation, allow_private=allow_private_targets,
            max_response_bytes=remaining_budget or limits.MAX_TOTAL_BYTES, origin=origin,
        )
        total_requests += 1
        fetch_ms = int((monotonic() - start) * 1000)

        if status == "cross_origin_redirect_blocked":
            instrumentation.record_skip("cross_origin_redirect_blocked")
            page = _extract_page(url, None, fetch_ms, limits, fetch_status="cross_origin_redirect_blocked")
            pages.append(page)
            continue
        if status == "blocked":
            continue  # already recorded via record_safety_block

        page = _extract_page(url, resp, fetch_ms, limits, fetch_status=status)
        pages.append(page)

        nbytes = len(resp.content) if (resp is not None and resp.content) else 0
        total_bytes += nbytes
        if total_bytes > limits.MAX_TOTAL_BYTES:
            instrumentation.record_skip("max_total_bytes_reached")
            break

        for link in page.internal_links:
            discovered.add(link)  # discovered != fetched: recorded even if never queued below
            if link in visited or link in to_visit:
                continue
            link_check = classify_url(link, allow_private=allow_private_targets)
            if not link_check.safe:
                instrumentation.record_safety_block(link, link_check.reason)
                continue
            depth_map[link] = depth_map.get(url, 0) + 1
            if depth_map[link] > limits.MAX_CRAWL_DEPTH:
                instrumentation.record_skip("max_crawl_depth_exceeded")
                continue
            to_visit.append(link)

    instrumentation.end_stage("acquisition")

    # Factual coverage breakdown: discovered/fetched/analyzed are NOT the same
    # number and must not be reported as if they were (Round-3 handout: "report
    # must not equate discovered = fetched = analyzed unless that is genuinely
    # true"). Computed from the actual outcome recorded on each PageArtifact,
    # not from a single len(pages) count reused three times.
    fetched_ok = [p for p in pages if p.status_code is not None and 200 <= p.status_code < 400]
    fetched_error = [p for p in pages if p.status_code is not None and p.status_code >= 400]
    blocked_pages = [p for p in pages if any(w.startswith("fetch_cross_origin_redirect_blocked") for w in p.warnings)]
    timed_out_pages = [p for p in pages if any(w == "fetch_timeout" for w in p.warnings)]
    failed_other_pages = [p for p in pages if p.status_code is None and p not in blocked_pages
                           and p not in timed_out_pages]
    skip_reason_counts = {}
    for reason in instrumentation.pages_skipped_reasons:
        skip_reason_counts[reason] = skip_reason_counts.get(reason, 0) + 1

    coverage_breakdown = {
        "urls_discovered": len(discovered),
        "urls_fetched_attempted": len(pages),
        "urls_fetched_ok": len(fetched_ok),
        "urls_fetched_error": len(fetched_error),
        "urls_blocked": len(blocked_pages) + len(instrumentation.safety_blocks),
        "urls_timed_out": len(timed_out_pages),
        "urls_failed_other": len(failed_other_pages),
        "urls_analyzed": len(fetched_ok),  # only pages with real, readable content are analyzable
        "urls_never_attempted": max(0, len(discovered) - len(pages)),
        "skip_reason_counts": skip_reason_counts,
    }

    return AuditArtifacts(
        site_url=site_url, normalized_origin=origin, pages=tuple(pages),
        robots_data=freeze_value({"allowed_general": robots_status in ("ok", "absent"),
                                   "status": robots_status, "conservative_fail_closed": conservative,
                                   "general_disallow": general_disallow,
                                   "ai_crawler_directives": ai_directives}),
        llms_txt_data=freeze_value(llms_txt_data), sitemap_data=freeze_value(sitemap_data),
        acquisition_metadata=freeze_value({"pages_crawled": len(pages), "total_bytes": total_bytes,
                                            "total_requests": total_requests,
                                            "coverage": coverage_breakdown}),
        warnings=tuple(top_warnings),
    )
