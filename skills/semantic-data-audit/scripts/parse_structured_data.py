#!/usr/bin/env python3
"""
Stage 2: Semantic Data & Fact Extraction Audit (parse_structured_data.py)
Unpacks nested @graph hierarchies, verifies baseline Organization/WebSite coverage,
and gates vertical-specific recommendations behind unambiguous on-page signals.
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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

JSONLD_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.DOTALL | re.IGNORECASE,
)

SIGNALS = {
    "FAQPage": {
        "pattern": re.compile(
            r"<details|<summary|\b(frequently\s+asked\s+questions|faq|common\s+questions)\b",
            re.IGNORECASE,
        ),
        "target_schema": "FAQPage",
        "description": "Interactive Q&A or FAQ accordion structures",
    },
    "LocalBusiness": {
        "pattern": re.compile(
            r"href=[\"']tel:|(?:opening\s+hours|store\s+hours|mon-fri)\b",
            re.IGNORECASE,
        ),
        "target_schema": "LocalBusiness",
        "description": "Physical location, business hours, or contact telephone signals",
    },
    "BreadcrumbList": {
        "pattern": re.compile(
            r"aria-label=[\"']breadcrumb[\"']|class=[\"'][^\"']*breadcrumb[^\"']*[\"']|>\s*(?:&(?:gt|rsaquo|raquo|#8250|#62);|[/»›>])\s*<",
            re.IGNORECASE,
        ),
        "target_schema": "BreadcrumbList",
        "description": "Multi-tier hierarchical navigation breadcrumbs",
    },
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

def unpack_graph(obj):
    """Recursively unpack @graph arrays into a flat entity list while preserving nodes."""
    if isinstance(obj, list):
        result = []
        for item in obj:
            result.extend(unpack_graph(item))
        return result
    if isinstance(obj, dict):
        result = []
        if "@graph" in obj:
            node_props = {k: v for k, v in obj.items() if k != "@graph"}
            if "@type" in node_props:
                result.append(node_props)
            result.extend(unpack_graph(obj["@graph"]))
            return result
        return [obj]
    return []

def extract_jsonld_entities(html_content):
    """Extract all schema.org entities and syntax errors from raw HTML, flattening nested @graph hierarchies."""
    entities = []
    syntax_errors = []
    for raw in JSONLD_RE.findall(html_content):
        raw_str = raw.strip()
        if not raw_str:
            continue
        try:
            data = json.loads(raw_str)
            entities.extend(unpack_graph(data))
        except json.JSONDecodeError as err:
            snippet = raw_str[:80].replace("\n", " ")
            syntax_errors.append(f"JSON syntax error ({err.msg} at line {err.lineno}, col {err.colno}): '{snippet}...'")
        except Exception as err:
            syntax_errors.append(f"JSON parse error: {str(err)[:80]}")
    return entities, syntax_errors

def normalize_schema_type(t):
    """Normalize schema type string or URI (e.g. 'https://schema.org/Organization', 'schema:Organization' -> 'Organization')."""
    if not isinstance(t, str):
        return ""
    return t.strip().rsplit("/", 1)[-1].rsplit("#", 1)[-1].rsplit(":", 1)[-1]

def audit_schema_coverage(html_content, extracted_entities, syntax_errors=None):
    """Audit structured data: syntax errors, universal baseline, and gated vertical opportunities."""
    findings = []
    proactive = []

    # 0. Audit JSON-LD Syntax Errors (High Severity)
    if syntax_errors:
        for err_msg in syntax_errors:
            findings.append({
                "category": "structured_data",
                "title": "Malformed JSON-LD syntax prevents AI fact extraction",
                "severity": "high",
                "evidence": f"Encountered invalid JSON-LD script block: {err_msg}",
                "mechanism": "AI search engine parsers (Google, Perplexity, Bing) abort parsing when encountering invalid JSON syntax, causing the entire structured data block to be discarded.",
                "suggested_action": {
                    "summary": "Fix JSON syntax errors in application/ld+json script blocks.",
                    "priority": "high",
                    "implementation_detail": "Validate all JSON-LD snippets using a JSON linter or Google's Rich Results Test tool before deploying.",
                    "expected_outcome": "Valid JSON-LD parseability by automated AI crawlers.",
                },
            })

    found_types = set()
    for ent in extracted_entities:
        t = ent.get("@type")
        if isinstance(t, list):
            found_types.update(normalize_schema_type(x) for x in t if x)
        elif isinstance(t, str):
            norm = normalize_schema_type(t)
            if norm:
                found_types.add(norm)

    # 1. Universal Baseline: Organization or WebSite must be present
    has_baseline = any(t in found_types for t in ["Organization", "Corporation", "WebSite", "Brand"])
    if not has_baseline:
        findings.append({
            "category": "structured_data",
            "title": "Missing baseline entity schema (Organization or WebSite)",
            "severity": "high",
            "evidence": f"Found schemas: {list(found_types) or 'None'}. Lacks Organization or WebSite definition.",
            "mechanism": "AI search engines require baseline entity definitions to anchor brand authority in their knowledge graphs.",
            "suggested_action": {
                "summary": "Add baseline Organization and WebSite JSON-LD to the homepage.",
                "priority": "high",
                "implementation_detail": '{\n  "@context": "https://schema.org",\n  "@type": "Organization",\n  "name": "BrandName",\n  "url": "https://example.com",\n  "sameAs": []\n}',
                "expected_outcome": "Immediate recognition of brand entity node by AI crawlers.",
            },
        })

    # 2. Generalized Gated Vertical Schemas: Proactive only when on-page signals exist
    # Product check: requires price AND high-intent cart action within a localized proximity window (<= 400 chars)
    # to distinguish true e-commerce product listings from marketing calculators or payment gateway copy.
    if "Product" not in found_types:
        price_matches = list(re.finditer(r"[\$€£₹]\s*\d+(?:\.\d{2})?", html_content))
        cart_matches = list(re.finditer(r"\b(add\s+to\s+cart|buy\s+now|in\s+stock|sku|order\s+now)\b", html_content, re.IGNORECASE))
        proximate_pair = None
        for pm in price_matches:
            for cm in cart_matches:
                if abs(pm.start() - cm.start()) <= 400:
                    proximate_pair = (pm.group(0), cm.group(0))
                    break
            if proximate_pair:
                break
        if proximate_pair:
            proactive.append({
                "title": "Add Product schema to match detected on-page content",
                "impact": "low",
                "rationale": f"Detected e-commerce transactional signals on-page ('{proximate_pair[0]}' with '{proximate_pair[1]}'), but no corresponding Product JSON-LD was declared.",
                "suggested_action": "Structure this content using schema.org/Product so AI assistants can extract exact specifications and pricing without hallucination.",
            })

    # Other vertical signals (FAQPage, LocalBusiness, BreadcrumbList)
    for vertical, conf in SIGNALS.items():
        if conf["target_schema"] not in found_types:
            match = conf["pattern"].search(html_content)
            if match:
                snippet = match.group(0).strip()[:40]
                proactive.append({
                    "title": f"Add {conf['target_schema']} schema to match detected on-page content",
                    "impact": "low",
                    "rationale": f"Detected {conf['description']} on-page (e.g., '{snippet}'), but no corresponding {conf['target_schema']} JSON-LD was declared.",
                    "suggested_action": f"Structure this content using schema.org/{conf['target_schema']} so AI assistants can extract exact specifications without hallucination.",
                })

    return findings, proactive

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: parse_structured_data.py <URL>\n")
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
                "category": "structured_data",
                "title": f"Target URL unreachable (HTTP {e.code})",
                "severity": "critical",
                "evidence": f"Failed to fetch {target_url}: HTTP {e.code} {e.reason}.",
                "mechanism": "AI search assistants cannot extract structured data from an unreachable URL.",
                "suggested_action": {
                    "summary": "Ensure target URL returns HTTP 200 OK to web clients.",
                    "priority": "critical",
                    "implementation_detail": f"Verify server availability for {target_url}.",
                    "expected_outcome": "URL becomes accessible for structured data parsing.",
                },
            })
            print(json.dumps({"findings": findings, "proactive_recommendations": proactive}, indent=2))
            return
        except Exception as e:
            findings.append({
                "category": "structured_data",
                "title": "Target URL connection failure or timeout",
                "severity": "critical",
                "evidence": f"Failed to connect to {target_url}: {str(e)[:100]}.",
                "mechanism": "AI search crawlers cannot extract structured facts if the domain network connection fails.",
                "suggested_action": {
                    "summary": "Verify domain DNS resolution and network availability.",
                    "priority": "critical",
                    "implementation_detail": f"Check DNS and server connectivity for {target_url}.",
                    "expected_outcome": "Successful network connections by web agents.",
                },
            })
            print(json.dumps({"findings": findings, "proactive_recommendations": proactive}, indent=2))
            return

    # 1. Extract JSON-LD entities and detect syntax errors
    entities, syntax_errors = extract_jsonld_entities(html_content)

    # 2. Audit syntax errors, baseline and gated vertical coverage
    schema_findings, schema_proactive = audit_schema_coverage(html_content, entities, syntax_errors)
    findings.extend(schema_findings)
    proactive.extend(schema_proactive)

    output = {"findings": findings, "proactive_recommendations": proactive}
    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
