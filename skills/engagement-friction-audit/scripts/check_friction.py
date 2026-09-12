#!/usr/bin/env python3
"""
Stage 4: Visitor Retention & Engagement Friction Audit (check_friction.py)
Audits mobile responsive viewport configuration, intrusive interstitial overlays/modals,
and fast email capture formatting for inbox AI summarizers (Apple Intelligence Mail, Gmail Gemini, Appendix F).
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

def audit_friction_and_email(html_content):
    """Audit mobile viewport, intrusive popups, and Appendix F email capture signals."""
    findings = []
    proactive = []

    # Head slicing for viewport check to avoid scanning large payloads
    head_content = html_content[:65536]

    # 1. Viewport Meta Tag Check (Order-resilient attribute inspection)
    meta_tags = get_meta_tags(head_content)
    has_viewport = any(m.get("name", "").lower() == "viewport" for m in meta_tags)
    if not has_viewport:
        findings.append({
            "category": "user_experience",
            "title": "Missing mobile responsive viewport tag",
            "severity": "medium",
            "evidence": "No <meta name='viewport'> tag detected in <head>.",
            "mechanism": "Mobile visitors referred by mobile AI assistants (e.g. ChatGPT iOS) will bounce immediately due to unreadable unscaled desktop layout.",
            "suggested_action": {
                "summary": "Add responsive viewport tag.",
                "priority": "medium",
                "implementation_detail": '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
                "expected_outcome": "Eliminates immediate mobile bounce upon arrival.",
            },
        })

    # 2. Intrusive Modal / Overlay Detection
    modal_patterns = re.compile(r'class=[\"\'][^\"\']*(?:modal-backdrop|overlay-active|newsletter-popup|interstitial)[^\"\']*[\"\']', re.IGNORECASE)
    if modal_patterns.search(html_content):
        findings.append({
            "category": "user_experience",
            "title": "Intrusive modal or overlay patterns detected in markup",
            "severity": "medium",
            "evidence": "Markup contains classes matching intrusive modal/interstitial patterns.",
            "mechanism": "Visitors following AI citations seek immediate answers; aggressive overlays trigger instant bounces back to the AI assistant.",
            "suggested_action": {
                "summary": "Delay non-essential modals until user demonstrates engagement.",
                "priority": "medium",
                "implementation_detail": "Trigger promotional popups only on exit intent or after 45+ seconds of scroll engagement.",
                "expected_outcome": "Reduced referral bounce rate from AI search citations.",
            },
        })

    # 3. Appendix F: Fast, Non-Blocking Email Capture & AI Summarization Check
    html_lower = html_content.lower()
    has_form = "<form" in html_lower
    has_email_input = (
        'type="email"' in html_lower or
        "type='email'" in html_lower or
        'name="email"' in html_lower or
        "name='email'" in html_lower or
        'placeholder="email' in html_lower or
        "placeholder='email" in html_lower
    )
    has_subscribe_intent = (
        "subscribe" in html_lower or
        "newsletter" in html_lower or
        "mailing list" in html_lower
    )

    if has_form and (has_email_input or has_subscribe_intent):
        proactive.append({
            "title": "Optimize outbound email formatting for inbox AI summarizers (Appendix F)",
            "impact": "low",
            "rationale": "Site collects email subscribers, but modern email clients (Apple Intelligence Mail, Gmail Gemini) automatically summarize inbound marketing emails for recipients.",
            "suggested_action": "Format outbound emails with clean multipart/plain-text fallbacks, front-load the primary value proposition and CTA within the first 3 lines, and avoid burying key offers exclusively inside promotional banner images.",
        })

    # 4. Deep-Link Navigation Accessibility (clean path routing vs hash-only fragments)
    hash_routing_matches = re.findall(r'href=[\"\']#(?:\/|!)[^\"\']*[\"\']', html_content, re.IGNORECASE)
    if len(hash_routing_matches) >= 2:
        findings.append({
            "category": "user_experience",
            "title": "Hash-based client routing impairs direct deep-link citation navigation",
            "severity": "medium",
            "evidence": f"Detected {len(hash_routing_matches)} navigation links using client hash routing (e.g. '{hash_routing_matches[0]}').",
            "mechanism": "AI search assistants cite direct path URLs. Hash-based routing schemes fail when automated crawlers or visitors navigate directly to deep paths, causing 404s or reset to homepage.",
            "suggested_action": {
                "summary": "Migrate from hash routing to HTML5 History API (pushState) path routing.",
                "priority": "medium",
                "implementation_detail": "Configure client router (e.g. React Router BrowserRouter instead of HashRouter) and server rewrite rules to serve clean path URLs.",
                "expected_outcome": "Seamless direct-destination navigation from AI search citations.",
            },
        })

    # 5. Semantic Heading Hierarchy Integrity (Multiple H1 consolidation)
    h1_count = len(re.findall(r"<h1\b", html_content, re.IGNORECASE))
    if h1_count > 1:
        proactive.append({
            "title": f"Consolidate multiple ({h1_count}) H1 headings into a single document anchor",
            "impact": "low",
            "rationale": f"Found {h1_count} separate <h1> tags. Using multiple H1s creates ambiguity for AI crawlers identifying the primary document topic.",
            "suggested_action": "Retain a single top-level <h1> for the primary title and downgrade section headers to <h2> or <h3>.",
        })

    return findings, proactive

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: check_friction.py <URL>\n")
        sys.exit(1)

    target_url = sys.argv[1]
    findings = []
    proactive = []

    # Cache-first fetch: reuse HTML retrieved by check_access.py if available
    html_content = None
    cache_path = "/tmp/audit_runs/page.html"
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8", errors="replace") as cf:
                html_content = cf.read()
        except OSError:
            html_content = None

    if html_content is None:
        try:
            html_content, final_url, status = fetch_html(target_url, timeout=10)
        except urllib.error.HTTPError as e:
            findings.append({
                "category": "user_experience",
                "title": f"Target URL unreachable (HTTP {e.code})",
                "severity": "critical",
                "evidence": f"Failed to fetch {target_url}: HTTP {e.code} {e.reason}.",
                "mechanism": "AI search assistants cannot evaluate user experience on an unreachable URL.",
                "suggested_action": {
                    "summary": "Ensure target URL returns HTTP 200 OK to web clients.",
                    "priority": "critical",
                    "implementation_detail": f"Verify server availability for {target_url}.",
                    "expected_outcome": "URL becomes accessible for user experience evaluation.",
                },
            })
            print(json.dumps({"findings": findings, "proactive_recommendations": proactive}, indent=2))
            return
        except Exception as e:
            findings.append({
                "category": "user_experience",
                "title": "Target URL connection failure or timeout",
                "severity": "critical",
                "evidence": f"Failed to connect to {target_url}: {str(e)[:100]}.",
                "mechanism": "AI search crawlers cannot evaluate visitor friction if the domain network connection fails.",
                "suggested_action": {
                    "summary": "Verify domain DNS resolution and network availability.",
                    "priority": "critical",
                    "implementation_detail": f"Check DNS and server connectivity for {target_url}.",
                    "expected_outcome": "Successful network connections by web agents.",
                },
            })
            print(json.dumps({"findings": findings, "proactive_recommendations": proactive}, indent=2))
            return

    friction_findings, friction_proactive = audit_friction_and_email(html_content)
    findings.extend(friction_findings)
    proactive.extend(friction_proactive)

    output = {"findings": findings, "proactive_recommendations": proactive}
    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
