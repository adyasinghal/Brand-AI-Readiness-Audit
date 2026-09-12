#!/usr/bin/env python3
"""
Stage 1: Crawl & Machine Access Audit (check_access.py)
Audits robots.txt AI bot exclusions, sitemap.xml availability and lastmod freshness,
meta robots noindex directives, and Client-Side Rendering (CSR) single-page application render gaps.
Pure Python 3 stdlib - zero external dependencies.
"""

import sys
import os
import json
import re
import urllib.request
import urllib.error
import urllib.parse
import ssl
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.robotparser import RobotFileParser

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

AI_BOTS = [
    "GPTBot", "ChatGPT-User", "ClaudeBot", "anthropic-ai",
    "PerplexityBot", "Google-Extended", "Applebot-Extended",
    "Amazonbot", "Bytespider", "CCBot", "cohere-ai", "Meta-ExternalAgent",
]

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

def check_ai_bot_access(robots_txt_content, target_path="/"):
    """Evaluate robots.txt permissions for known AI search and retrieval bots."""
    rp = RobotFileParser()
    rp.parse(robots_txt_content.splitlines())
    blocked = []
    for bot in AI_BOTS:
        if not rp.can_fetch(bot, target_path):
            blocked.append(bot)
    return blocked

def audit_sitemap(base_url, robots_content):
    """Audit sitemap discovery, HTTP availability, and <lastmod> freshness."""
    findings = []
    proactive = []
    
    sitemap_url = None
    if robots_content:
        for line in robots_content.splitlines():
            line_str = line.strip()
            if line_str.lower().startswith("sitemap:"):
                sitemap_url = line_str.split(":", 1)[1].strip()
                break
    if not sitemap_url:
        sitemap_url = urllib.parse.urljoin(base_url, "/sitemap.xml")

    try:
        xml_text, final_url, status = fetch_html(sitemap_url, timeout=8)
    except urllib.error.HTTPError as e:
        findings.append({
            "category": "crawlability",
            "title": f"Sitemap returned HTTP {e.code}",
            "severity": "medium",
            "evidence": f"Target sitemap {sitemap_url} responded with HTTP error {e.code}: {e.reason}.",
            "mechanism": "AI search engines use sitemaps to discover canonical URL inventories.",
            "suggested_action": {
                "summary": "Ensure sitemap.xml is accessible and returns HTTP 200.",
                "priority": "medium",
                "implementation_detail": f"Configure web server to route {sitemap_url} to valid XML.",
                "expected_outcome": "Complete URL indexation by automated search agents.",
            }
        })
        return findings, proactive
    except Exception as e:
        findings.append({
            "category": "crawlability",
            "title": "Missing or inaccessible sitemap.xml",
            "severity": "medium",
            "evidence": f"Failed to fetch {sitemap_url}: {str(e)[:80]}",
            "mechanism": "Without a valid sitemap, AI crawlers must discover pages through heuristic link traversal.",
            "suggested_action": {
                "summary": "Publish an XML sitemap at /sitemap.xml and reference it in robots.txt.",
                "priority": "medium",
                "implementation_detail": f"Generate sitemap.xml and add 'Sitemap: {base_url}/sitemap.xml' to robots.txt.",
                "expected_outcome": "Immediate discovery of new and updated pages by AI bots.",
            }
        })
    # Guard against soft-404: single-page applications or web servers returning HTML for /sitemap.xml
    stripped_lower = xml_text.strip().lower()
    if stripped_lower.startswith(("<!doctype", "<html")):
        findings.append({
            "category": "crawlability",
            "title": "Sitemap returns HTML document instead of XML (soft-404)",
            "severity": "medium",
            "evidence": f"Target sitemap endpoint {sitemap_url} responded with an HTML webpage instead of XML markup.",
            "mechanism": "AI search crawlers expect valid XML at sitemap endpoints; HTML responses prevent canonical URL discovery.",
            "suggested_action": {
                "summary": "Publish a valid XML sitemap at /sitemap.xml.",
                "priority": "medium",
                "implementation_detail": f"Configure server routing so {sitemap_url} serves valid XML instead of an HTML catch-all page.",
                "expected_outcome": "Automated discovery of canonical page inventory by AI crawlers.",
            }
        })
        return findings, proactive

    try:
        root = ET.fromstring(xml_text.lstrip())
        lastmods = []
        for elem in root.iter():
            if elem.tag.endswith("lastmod") and elem.text:
                lastmods.append(elem.text.strip())

        if not lastmods:
            proactive.append({
                "title": "Add <lastmod> timestamps to sitemap.xml",
                "impact": "low",
                "rationale": "Sitemap contains URLs but lacks <lastmod> dates, preventing AI crawlers from prioritizing recently updated content.",
                "suggested_action": "Configure CMS to emit ISO 8601 <lastmod> timestamps on content updates."
            })
        else:
            years = [int(m.group(1)) for lm in lastmods if (m := re.match(r"^(\d{4})", lm))]
            if years:
                latest_year = max(years)
                current_year = datetime.now().year
                if current_year - latest_year >= 2:
                    findings.append({
                        "category": "crawlability",
                        "title": f"Stale sitemap content (latest update {latest_year})",
                        "severity": "medium",
                        "evidence": f"Sitemap lastmod dates show no updates since {latest_year} ({current_year - latest_year} years behind current year {current_year}).",
                        "mechanism": "AI search engines deprioritize crawling domains with stale sitemap timestamps.",
                        "suggested_action": {
                            "summary": "Refresh sitemap with current content modification timestamps.",
                            "priority": "medium",
                            "implementation_detail": f"Ensure active pages reflect current modification dates (e.g. {current_year}).",
                            "expected_outcome": "Restores crawl priority for live AI agents.",
                        }
                    })
    except ET.ParseError:
        findings.append({
            "category": "crawlability",
            "title": "Malformed sitemap.xml syntax",
            "severity": "medium",
            "evidence": "Sitemap endpoint returned invalid or unparseable XML markup.",
            "mechanism": "Automated crawlers abort sitemap parsing if XML syntax is invalid.",
            "suggested_action": {
                "summary": "Validate and fix sitemap.xml formatting.",
                "priority": "medium",
                "implementation_detail": "Validate sitemap markup against the sitemaps.org 0.9 schema.",
                "expected_outcome": "Valid XML parsing by automated crawlers.",
            }
        })

    return findings, proactive

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: check_access.py <URL>\n")
        sys.exit(1)

    target_url = sys.argv[1]
    findings = []
    proactive = []

    # 1. Fetch robots.txt and audit AI bot access
    robots_url = urllib.parse.urljoin(target_url, "/robots.txt")
    robots_txt = ""
    try:
        robots_txt, _, status = fetch_html(robots_url, timeout=8)
        blocked_bots = check_ai_bot_access(robots_txt)
        if blocked_bots:
            findings.append({
                "category": "crawlability",
                "title": f"Robots.txt blocks AI search crawlers ({', '.join(blocked_bots[:3])})",
                "severity": "critical",
                "evidence": f"Tested {len(AI_BOTS)} AI crawlers against /robots.txt; {len(blocked_bots)} blocked: {', '.join(blocked_bots)}.",
                "mechanism": "AI assistants using live web retrieval respect robots.txt exclusions. Blocked agents cannot fetch, index, or cite any page on this domain.",
                "suggested_action": {
                    "summary": "Allow AI search crawlers in robots.txt.",
                    "priority": "critical",
                    "implementation_detail": "".join([f"User-agent: {b}\nAllow: /\n\n" for b in blocked_bots[:2]]).strip(),
                    "expected_outcome": "Immediate eligibility for real-time citation in ChatGPT and Claude web search.",
                }
            })
    except Exception:
        pass

    # 2. Audit sitemap.xml
    sm_findings, sm_proactive = audit_sitemap(target_url, robots_txt)
    findings.extend(sm_findings)
    proactive.extend(sm_proactive)

    # 3. Fetch target page and audit CSR shell and meta robots (Order-Resilient & Network-Protected)
    try:
        html_content, final_url, status = fetch_html(target_url, timeout=10)
    except urllib.error.HTTPError as e:
        findings.append({
            "category": "crawlability",
            "title": f"Target URL unreachable (HTTP {e.code})",
            "severity": "critical",
            "evidence": f"Failed to fetch {target_url}: HTTP {e.code} {e.reason}.",
            "mechanism": "AI search assistants cannot retrieve or analyze an unreachable URL.",
            "suggested_action": {
                "summary": "Ensure target URL returns HTTP 200 OK to web clients.",
                "priority": "critical",
                "implementation_detail": f"Investigate web server routing, security policies, and firewall rules for {target_url}.",
                "expected_outcome": "URL becomes accessible to search crawlers.",
            },
        })
        print(json.dumps({"findings": findings, "proactive_recommendations": proactive}, indent=2))
        return
    except Exception as e:
        findings.append({
            "category": "crawlability",
            "title": "Target URL connection failure or timeout",
            "severity": "critical",
            "evidence": f"Failed to connect to {target_url}: {str(e)[:100]}.",
            "mechanism": "AI search crawlers cannot evaluate pages that fail network connections or time out.",
            "suggested_action": {
                "summary": "Verify domain DNS resolution and network availability.",
                "priority": "critical",
                "implementation_detail": f"Check DNS A/AAAA records, server health, and SSL certificate validity for {target_url}.",
                "expected_outcome": "Successful network connections by web agents.",
            },
        })
        print(json.dumps({"findings": findings, "proactive_recommendations": proactive}, indent=2))
        return

    head_content = html_content[:65536]

    # Meta robots check: Order-resilient using attribute dictionary
    meta_tags = get_meta_tags(head_content)
    has_noindex = any(
        m.get("name", "").lower() == "robots" and "noindex" in m.get("content", "").lower()
        for m in meta_tags
    )
    if has_noindex:
        findings.append({
            "category": "crawlability",
            "title": "Meta robots explicitly disallows search indexing ('noindex')",
            "severity": "critical",
            "evidence": "Detected <meta name='robots' content='noindex'> directive in <head>.",
            "mechanism": "The noindex directive instructs search bots to discard the page from index databases.",
            "suggested_action": {
                "summary": "Remove noindex directive from production pages.",
                "priority": "critical",
                "implementation_detail": "Replace 'noindex' with 'index, follow' in the robots meta tag.",
                "expected_outcome": "Restores search indexation across all web agents.",
            }
        })

    # CSR shell check: Distinguish between 100% empty shell (Critical) and partial render gap (High)
    body_m = re.search(r"<body[^>]*>(.*?)</body>", html_content, re.DOTALL | re.IGNORECASE)
    body_html = body_m.group(1) if body_m else html_content
    text_content = re.sub(r"<script[^>]*>.*?</script>", "", body_html, flags=re.DOTALL | re.IGNORECASE)
    text_content = re.sub(r"<style[^>]*>.*?</style>", "", text_content, flags=re.DOTALL | re.IGNORECASE)
    text_clean = re.sub(r"<[^>]+>", " ", text_content).strip()

    has_bundle = bool(re.search(r"<script[^>]+src=[\"'][^\"']*(?:app|bundle|main|chunk)[^\"']*\.js", html_content, re.IGNORECASE))
    if len(text_clean) < 50 and has_bundle:
        findings.append({
            "category": "crawlability",
            "title": "100% empty Client-Side Rendering (CSR) single-page application shell",
            "severity": "critical",
            "evidence": f"Body text contains only {len(text_clean)} visible characters before client-side JS execution.",
            "mechanism": "AI search bots without headless browser execution see a blank page, making the entire site invisible.",
            "suggested_action": {
                "summary": "Implement Server-Side Rendering (SSR) or pre-rendering.",
                "priority": "critical",
                "implementation_detail": "Use Next.js SSR, Nuxt, or static site generation (SSG) to emit semantic HTML in initial HTTP response.",
                "expected_outcome": "Full page content immediately readable by non-JS crawlers.",
            }
        })
    elif len(text_clean) < 300 and has_bundle:
        findings.append({
            "category": "crawlability",
            "title": "Partial CSR render gap: sparse initial HTML shell with primary content locked in client JavaScript",
            "severity": "high",
            "evidence": f"Body text contains only {len(text_clean)} visible characters before JS execution with active script bundle.",
            "mechanism": "AI crawlers that do not execute client scripts see an incomplete page skeleton, causing partial indexation.",
            "suggested_action": {
                "summary": "Pre-render core article text, specifications, and navigation on the server.",
                "priority": "high",
                "implementation_detail": "Ensure primary product/brand text is present in the server-rendered HTML payload.",
                "expected_outcome": "Comprehensive factual extraction by automated AI crawlers.",
            }
        })

    # 4. Audit /llms.txt discovery (with Gzip decompression, redirect and soft-404 protection)
    llms_url = urllib.parse.urljoin(target_url, "/llms.txt")
    has_llms = False
    try:
        llms_text, final_url, llms_status = fetch_html(llms_url, timeout=5)
        # Verify request did not redirect away to homepage or 404 handler
        if llms_status == 200 and final_url.rstrip("/").endswith("/llms.txt"):
            text_sample = llms_text.strip().lower()
            # Verify payload is markdown/text rather than an HTML soft-404/homepage document
            if not text_sample.startswith("<!doctype") and not text_sample.startswith("<html") and len(text_sample) >= 10:
                has_llms = True
    except Exception:
        has_llms = False

    if not has_llms:
        proactive.append({
            "title": "Publish an /llms.txt discovery file for AI search crawlers",
            "impact": "low",
            "rationale": "Domain lacks an /llms.txt manifest, which modern AI search assistants use to navigate primary markdown summaries, documentation paths, and authoritative brand directories.",
            "suggested_action": "Publish a clean markdown manifest at /llms.txt listing your core value propositions, API/documentation links, and high-priority brand resources.",
        })

    # Cache fetched HTML for downstream scripts to avoid redundant HTTP round-trips
    try:
        cache_dir = "/tmp/audit_runs"
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, "page.html")
        with open(cache_path, "w", encoding="utf-8", errors="replace") as cf:
            cf.write(html_content)
    except OSError:
        pass  # Non-fatal: downstream scripts will live-fetch as fallback

    output = {"findings": findings, "proactive_recommendations": proactive}
    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
