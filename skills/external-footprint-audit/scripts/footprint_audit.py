#!/usr/bin/env python3
"""
footprint_audit.py - Optional external footprint and corroboration audit.

Consumes site_snapshot.json and checks the site's presence in the wider web
using at most three keyless, read-only queries to public endpoints:

  1. Common Crawl index listing (which crawl is newest)
  2. Common Crawl CDX lookup for the audited domain
  3. Wikipedia OpenSearch for the brand name

This is the only skill besides crawl-render-audit that opens a network
connection, and it never touches the audited site itself. It is OFF by
default; the orchestrator runs it only when invoked with --external-checks.
Every probe degrades gracefully: an unreachable or slow endpoint produces a
note in the output, never an error and never a finding.

Usage:
  python3 footprint_audit.py --workdir ./audit_work
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request

USER_AGENT = "BrandAuditBot/1.0 (read-only site audit; contact: hackathon submission)"
PROBE_TIMEOUT = 10
CC_COLLINFO = "https://index.commoncrawl.org/collinfo.json"
WIKI_OPENSEARCH = "https://en.wikipedia.org/w/api.php?action=opensearch&limit=5&format=json&search="


def finding(check, title, severity, evidence, action_summary, priority=None, effort="medium"):
    return {
        "check": check,
        "title": title,
        "severity": severity,
        "evidence": evidence,
        "suggested_action": {"summary": action_summary, "priority": priority or severity},
        "effort": effort,
        "source_skill": "external-footprint-audit",
    }


def get_json(url):
    """Fetch a public JSON endpoint. Returns (data, error_note)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT) as resp:
            body = resp.read(2_000_000).decode("utf-8", errors="replace")
        return json.loads(body), None
    except Exception as e:
        return None, "{} unreachable ({}: {})".format(url.split("?")[0], type(e).__name__, e)


def get_text(url):
    """Fetch a public text endpoint. Returns (text, error_note)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT) as resp:
            return resp.read(2_000_000).decode("utf-8", errors="replace"), None
    except Exception as e:
        return None, "{} unreachable ({}: {})".format(url.split("?")[0], type(e).__name__, e)


def derive_brand_token(snap):
    pages = [p for p in snap.get("pages", []) if p.get("status") == 200 and p.get("features")]
    if not pages:
        return ""
    f = pages[0]["features"]
    site_name = f.get("meta", {}).get("og:site_name") or ""
    title = f.get("title", "")
    token = (site_name or title.split("|")[0].split(" - ")[0]).strip()
    return token[:80]


def main():
    ap = argparse.ArgumentParser(description="External footprint audit (opt-in)")
    ap.add_argument("--workdir", default="./audit_work")
    args = ap.parse_args()

    snap_path = os.path.join(args.workdir, "site_snapshot.json")
    if not os.path.exists(snap_path):
        print("external-footprint-audit: site_snapshot.json not found; run crawl-render-audit first", file=sys.stderr)
        return 2
    with open(snap_path, encoding="utf-8") as fh:
        snap = json.load(fh)

    host = snap.get("host", "")
    host = host[4:] if host.startswith("www.") else host
    findings, notes = [], []

    # ---- Probe 1 + 2: Common Crawl presence (EX-01) ---------------------
    if host and "." in host and not host.startswith("localhost") and not host.split(":")[0].replace(".", "").isdigit():
        collinfo, err = get_json(CC_COLLINFO)
        if err:
            notes.append(err)
        else:
            cdx_api = None
            if isinstance(collinfo, list) and collinfo and isinstance(collinfo[0], dict):
                cdx_api = collinfo[0].get("cdx-api")
            if not cdx_api:
                notes.append("Common Crawl collinfo.json had an unexpected shape; skipping the presence check")
            else:
                query = "{}?url={}&matchType=domain&limit=1&output=json".format(
                    cdx_api, urllib.parse.quote(host, safe=""))
                body, err2 = get_text(query)
                if err2:
                    notes.append(err2)
                elif not body or not body.strip():
                    findings.append(finding(
                        "EX-01", "Domain absent from the Common Crawl web corpus", "medium",
                        "The latest Common Crawl index ({}) contains zero captures for {}. Common Crawl is the open corpus many AI training and retrieval pipelines start from; a domain absent from it is invisible to that entire downstream ecosystem regardless of how good the on-site content is.".format(
                            collinfo[0].get("id", "latest"), host),
                        "Verify the site is crawlable (robots.txt allows CCBot, no bot wall for well-behaved crawlers), submit the sitemap to search engines, and earn a few inbound links so open-web crawlers discover the domain.",
                        effort="medium"))
                else:
                    notes.append("Common Crawl {}: {} is present in the corpus".format(
                        collinfo[0].get("id", "latest"), host))
    else:
        notes.append("host '{}' is local or non-public; external presence checks skipped".format(host))

    # ---- Probe 3: Wikipedia entity match (EX-02) ------------------------
    brand = derive_brand_token(snap)
    if brand and len(brand) >= 3 and re.search(r"[a-zA-Z]", brand):
        data, err = get_json(WIKI_OPENSEARCH + urllib.parse.quote(brand))
        if err:
            notes.append(err)
        elif isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
            titles = [str(t).lower() for t in data[1]]
            match = any(brand.lower() == t or brand.lower() in t for t in titles)
            if not match:
                findings.append(finding(
                    "EX-02", "No Wikipedia entity found for the brand name", "low",
                    "Wikipedia OpenSearch returned no article matching '{}'. This is normal for smaller organizations and is listed as an opportunity, not a defect: knowledge-graph entries (Wikipedia, Wikidata) are the corroboration sources machines weight most when resolving who an entity is.".format(brand),
                    "If the organization meets notability criteria, ensure a neutral Wikipedia/Wikidata presence exists; otherwise strengthen the substitutes machines fall back on: Organization JSON-LD with sameAs, and consistent profiles on established platforms.",
                    effort="high"))
            else:
                notes.append("Wikipedia has a matching entity for '{}'".format(brand))
    else:
        notes.append("no usable brand token derived from the homepage; Wikipedia check skipped")

    with open(os.path.join(args.workdir, "footprint_findings.json"), "w", encoding="utf-8") as fh:
        json.dump({"skill": "external-footprint-audit", "findings": findings, "notes": notes},
                  fh, ensure_ascii=False, indent=2)

    print("external-footprint-audit: {} findings; {}".format(len(findings), "; ".join(notes) or "all probes answered"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
