#!/usr/bin/env python3
"""
Stage 3: Entity Authority & Identity Disambiguation (check_entity_trust.py)
Audits brand naming consistency across <title>, <h1>, and OpenGraph tags,
evaluates OpenGraph presence, footer copyright freshness, and Organization sameAs authoritative disambiguation.
Pure Python 3 stdlib - zero external dependencies.
"""

import sys
import os
import json
import re
import urllib.request
import urllib.error
import ssl
import gzip
from datetime import datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def safe_fetch(url, timeout=10):
    """Fetch URL with a modern browser User-Agent and verified SSL fallback."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.URLError as e:
        if isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError):
            sys.stderr.write(f"[WARN] SSL verification failed for {url}; retrying without verification.\n")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return urllib.request.urlopen(req, timeout=timeout, context=ctx)
        raise

def fetch_html(url, timeout=10):
    """Fetch URL and return decoded string, handling forced Gzip compression automatically."""
    resp = safe_fetch(url, timeout=timeout)
    raw_bytes = resp.read()
    if raw_bytes.startswith(b"\x1f\x8b"):
        raw_bytes = gzip.decompress(raw_bytes)
    return raw_bytes.decode("utf-8", errors="replace"), resp.geturl(), resp.status

def get_meta_tags(html):
    """Extract all <meta> tags into attribute dictionaries, independent of attribute order, quotes, or unquoted values."""
    tags = []
    for meta_str in re.findall(r"<meta\b([^>]*)>", html, re.IGNORECASE):
        matches = re.findall(r'''(\w[\w:-]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>]+))''', meta_str)
        attrs = {k.lower(): (v1 or v2 or v3) for k, v1, v2, v3 in matches}
        if attrs:
            tags.append(attrs)
    return tags

def normalize_schema_type(t):
    """Normalize schema type string or URI (e.g. 'https://schema.org/Organization', 'schema:Organization' -> 'Organization')."""
    if not isinstance(t, str):
        return ""
    return t.strip().rsplit("/", 1)[-1].rsplit("#", 1)[-1].rsplit(":", 1)[-1]

def extract_organization(html_content):
    """Extract Organization/Brand entity from JSON-LD scripts in HTML, supporting multi-typed array nodes and full URIs."""
    for raw in re.findall(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", html_content, re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(raw.strip())
            candidates = data.get("@graph", [data]) if isinstance(data, dict) else data
            for node in candidates if isinstance(candidates, list) else [candidates]:
                if isinstance(node, dict):
                    node_types = node.get("@type")
                    raw_list = node_types if isinstance(node_types, list) else [node_types]
                    type_set = {normalize_schema_type(t) for t in raw_list if t}
                    if type_set & {"Organization", "Corporation", "Brand", "LocalBusiness"}:
                        return node
        except (json.JSONDecodeError, AttributeError):
            continue
    return None

def audit_entity_trust(html_content, organization_entity=None):
    """Audit mechanical entity trust signals: Title/H1/OG consistency, OpenGraph presence, copyright freshness, sameAs links."""
    findings = []
    
    # Extract Organization locally if not passed from external caller
    organization_entity = organization_entity or extract_organization(html_content)
    
    # Decouple head (<title>, <meta>) and body (<h1>) slices to survive heavy CSS/JSON-LD heads (>64KB)
    head_end_m = re.search(r"</head>", html_content, re.IGNORECASE)
    head_end = head_end_m.end() if head_end_m else 65536
    head_content = html_content[:min(head_end, 262144)]

    body_start_m = re.search(r"<body\b[^>]*>", html_content, re.IGNORECASE)
    body_idx = body_start_m.end() if body_start_m else head_end
    body_slice = html_content[body_idx:body_idx + 131072]
    tail_content = html_content[-65536:] if len(html_content) > 65536 else html_content

    # 1. Brand Name Consistency across Title, H1, and OG:Title
    title_m = re.search(r"<title[^>]*>(.*?)</title>", head_content, re.IGNORECASE | re.DOTALL)
    h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", body_slice, re.IGNORECASE | re.DOTALL)
    if not h1_m:
        h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", html_content[:131072], re.IGNORECASE | re.DOTALL)

    title = title_m.group(1).strip() if title_m else ""
    h1 = h1_m.group(1).strip() if h1_m else ""
    h1_clean = re.sub(r"<[^>]+>", "", h1).strip()
    
    # Order-resilient OpenGraph metadata extraction (supporting both property="og:title" and name="og:title")
    meta_tags = get_meta_tags(head_content)
    og_title = next(
        (m.get("content", "").strip() for m in meta_tags 
         if (m.get("property", "").lower() == "og:title" or m.get("name", "").lower() == "og:title")),
        ""
    )

    # Check for complete brand name mismatch between primary tags or missing H1 entity anchor
    if title and h1_clean:
        title_tokens = set(re.findall(r"\b\w{4,}\b", title.lower()))
        h1_tokens = set(re.findall(r"\b\w{4,}\b", h1_clean.lower()))
        if title_tokens and h1_tokens and not (title_tokens & h1_tokens):
            findings.append({
                "category": "entity_trust",
                "title": "Brand naming divergence across Title and H1 headings",
                "severity": "medium",
                "evidence": f"Title: '{title}' vs H1: '{h1_clean}'. Zero common significant words found.",
                "mechanism": "Conflicting primary identifiers create entity ambiguity, causing AI summarizers to mislabel the brand name.",
                "suggested_action": {
                    "summary": "Align <title> and main <h1> to lead with the identical brand name.",
                    "priority": "medium",
                    "implementation_detail": f"Ensure '{h1_clean}' or canonical brand name is prominently featured in both <title> and <h1>.",
                    "expected_outcome": "Unambiguous entity identification in AI retrieval snippets.",
                },
            })
    elif not h1_clean and not h1_m:
        findings.append({
            "category": "entity_trust",
            "title": "Missing primary <h1> entity anchor heading",
            "severity": "medium",
            "evidence": "Zero <h1> headings identified in document markup to anchor core brand entity.",
            "mechanism": "Conversational AI engines and knowledge extractors rely on <h1> as the primary topic and brand anchor.",
            "suggested_action": {
                "summary": "Add a clear, top-level <h1> heading declaring the entity or page topic.",
                "priority": "medium",
                "implementation_detail": f"<h1>{title or 'Brand Name'}</h1>",
                "expected_outcome": "Definitive topical anchor for AI retrieval and knowledge graph extraction.",
            },
        })

    # 2. OpenGraph Tag Presence & Consistency Check (evaluates against H1 or Title anchor)
    if not og_title:
        findings.append({
            "category": "entity_trust",
            "title": "Missing OpenGraph metadata tags (og:title)",
            "severity": "medium",
            "evidence": "No <meta property='og:title'> detected in <head> markup.",
            "mechanism": "AI search engines and conversational preview engines rely on OpenGraph protocol tags to generate rich citation cards.",
            "suggested_action": {
                "summary": "Implement OpenGraph meta tags for title, description, and canonical URL.",
                "priority": "medium",
                "implementation_detail": f'<meta property="og:title" content="{h1_clean or title or "Brand Name"}">\n<meta property="og:type" content="website">',
                "expected_outcome": "Rich media preview card generation across AI chat interfaces.",
            },
        })
    elif h1_clean or title:
        target_name = h1_clean if h1_clean else title
        target_label = "H1 heading" if h1_clean else "<title> tag"
        og_tokens = set(re.findall(r"\b\w{4,}\b", og_title.lower()))
        target_tokens = set(re.findall(r"\b\w{4,}\b", target_name.lower()))
        if og_tokens and target_tokens and not (og_tokens & target_tokens):
            findings.append({
                "category": "entity_trust",
                "title": f"OpenGraph title diverges from main {target_label}",
                "severity": "medium",
                "evidence": f"OG Title: '{og_title}' vs {target_label}: '{target_name}'. Zero common significant words found.",
                "mechanism": "Conflicting entity metadata between social graph tags and page headings creates ambiguous entity profiles in AI summarizers.",
                "suggested_action": {
                    "summary": f"Align og:title tag with the primary {target_label} brand name.",
                    "priority": "medium",
                    "implementation_detail": f'<meta property="og:title" content="{target_name}">',
                    "expected_outcome": "Harmonized brand entity recognition across search and social citations.",
                },
            })

    # 3. Content Freshness: Copyright Year Check (searched within tail_content)
    current_year = datetime.now().year
    copy_m = re.search(r"(?:©|&copy;|copyright)\s*(?:(?:19|20)\d{2}\s*[-–—]\s*)?((?:19|20)\d{2})", tail_content, re.IGNORECASE)
    if copy_m:
        copy_year = int(copy_m.group(1))
        if current_year - copy_year >= 2:
            findings.append({
                "category": "entity_trust",
                "title": f"Stale copyright notice ({copy_year}) signals unmaintained domain",
                "severity": "medium",
                "evidence": f"Detected footer copyright year {copy_year} ({current_year - copy_year} years behind current year {current_year}).",
                "mechanism": "AI search agents use footer copyright recency as a heuristic for domain vitality. Stale years downgrade freshness confidence.",
                "suggested_action": {
                    "summary": f"Update footer copyright year to {current_year}.",
                    "priority": "medium",
                    "implementation_detail": f"Replace '© {copy_year}' with '© {current_year}' or dynamic server-side current year.",
                    "expected_outcome": "Restores recency signals for real-time web agents.",
                },
            })

    # 4. Organization sameAs Disambiguation
    if organization_entity:
        same_as = organization_entity.get("sameAs", [])
        if not same_as:
            findings.append({
                "category": "entity_trust",
                "title": "Missing Organization sameAs authoritative authority links",
                "severity": "high",
                "evidence": "Organization schema exists but contains no sameAs references.",
                "mechanism": "Without sameAs links to Wikipedia, Wikidata, LinkedIn, or official registers, AI cannot link the site to its canonical knowledge graph node.",
                "suggested_action": {
                    "summary": "Populate sameAs array in Organization JSON-LD.",
                    "priority": "high",
                    "implementation_detail": '"sameAs": ["https://www.linkedin.com/company/example", "https://www.wikidata.org/wiki/Q..."]',
                    "expected_outcome": "Knowledge graph disambiguation across major LLM foundation models.",
                },
            })

    return findings

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: check_entity_trust.py <URL>\n")
        sys.exit(1)

    target_url = sys.argv[1]
    findings = []
    proactive = []

    # Cache-first fetch: reuse HTML retrieved by check_access.py if target_url matches
    html_content = None
    cache_path = "/tmp/audit_runs/page.html"
    cache_url_path = "/tmp/audit_runs/page.url"
    if os.path.exists(cache_path) and os.path.exists(cache_url_path):
        try:
            with open(cache_url_path, "r", encoding="utf-8") as uf:
                cached_url = uf.read().strip()
            if cached_url == target_url:
                with open(cache_path, "r", encoding="utf-8", errors="replace") as cf:
                    html_content = cf.read()
        except OSError:
            html_content = None

    if html_content is None:
        try:
            html_content, final_url, status = fetch_html(target_url, timeout=10)
        except urllib.error.HTTPError as e:
            findings.append({
                "category": "entity_trust",
                "title": f"Target URL unreachable (HTTP {e.code})",
                "severity": "critical",
                "evidence": f"Failed to fetch {target_url}: HTTP {e.code} {e.reason}.",
                "mechanism": "AI search assistants cannot evaluate entity authority on an unreachable URL.",
                "suggested_action": {
                    "summary": "Ensure target URL returns HTTP 200 OK to web clients.",
                    "priority": "critical",
                    "implementation_detail": f"Verify server availability for {target_url}.",
                    "expected_outcome": "URL becomes accessible for entity trust verification.",
                },
            })
            print(json.dumps({"findings": findings, "proactive_recommendations": proactive}, indent=2))
            return
        except Exception as e:
            findings.append({
                "category": "entity_trust",
                "title": "Target URL connection failure or timeout",
                "severity": "critical",
                "evidence": f"Failed to connect to {target_url}: {str(e)[:100]}.",
                "mechanism": "AI search crawlers cannot evaluate entity authority if the domain fails network connection.",
                "suggested_action": {
                    "summary": "Verify domain DNS resolution and network availability.",
                    "priority": "critical",
                    "implementation_detail": f"Check DNS and server connectivity for {target_url}.",
                    "expected_outcome": "Successful network connections by web agents.",
                },
            })
            print(json.dumps({"findings": findings, "proactive_recommendations": proactive}, indent=2))
            return

    findings = audit_entity_trust(html_content)

    output = {"findings": findings, "proactive_recommendations": []}
    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
