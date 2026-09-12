#!/usr/bin/env python3
"""
freshness_audit.py - Freshness, corroboration, and entity-identity audit.

Consumes the site_snapshot.json produced by the crawl-render-audit skill and
checks whether the site's facts look current, corroborated across the wider
web, and attributable to an unambiguous entity. Writes freshness_findings.json.

Usage:
  python3 freshness_audit.py --workdir ./audit_work
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

STALE_MONTHS = 18
EXTERNAL_PROFILE_HOSTS = [
    "wikipedia.org", "wikidata.org", "linkedin.com", "github.com",
    "crunchbase.com", "x.com", "twitter.com", "facebook.com",
    "instagram.com", "youtube.com", "glassdoor.com", "trustpilot.com",
    "g2.com", "producthunt.com", "medium.com", "reddit.com",
]

MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
DATE_PATTERNS = [
    r"\b(20\d{2})-(\d{2})-(\d{2})\b",                                   # 2026-03-15
    r"\b(?:{m})\s+\d{{1,2}},?\s+(20\d{{2}})\b".format(m=MONTHS),        # March 15, 2026
    r"\b\d{{1,2}}\s+(?:{m}),?\s+(20\d{{2}})\b".format(m=MONTHS),        # 15 March 2026
]


def finding(check, title, severity, evidence, action_summary, priority=None, effort="medium"):
    return {
        "check": check,
        "title": title,
        "severity": severity,
        "evidence": evidence,
        "suggested_action": {"summary": action_summary, "priority": priority or severity},
        "effort": effort,
        "source_skill": "freshness-corroboration",
    }


def parse_iso_year(value):
    m = re.search(r"(20\d{2})", str(value))
    return int(m.group(1)) if m else None


def extract_years(text):
    years = []
    lowered = text.lower()
    for pat in DATE_PATTERNS:
        for m in re.finditer(pat, lowered, re.I):
            y = parse_iso_year(m.group(0))
            if y and 2000 <= y <= 2100:
                years.append(y)
    return years


def collect_jsonld_dates(pages):
    dates = []
    for p in pages:
        f = p.get("features")
        if not f:
            continue
        for item in f.get("jsonld_items", []):
            for key in ("datePublished", "dateModified"):
                if key in item:
                    y = parse_iso_year(item[key])
                    if y:
                        dates.append((p["url"], key, str(item[key])[:25], y))
        for key in ("article:published_time", "article:modified_time"):
            if key in f.get("meta", {}):
                y = parse_iso_year(f["meta"][key])
                if y:
                    dates.append((p["url"], key, str(f["meta"][key])[:25], y))
    return dates


def main():
    ap = argparse.ArgumentParser(description="Freshness and corroboration audit")
    ap.add_argument("--workdir", default="./audit_work")
    args = ap.parse_args()

    snap_path = os.path.join(args.workdir, "site_snapshot.json")
    if not os.path.exists(snap_path):
        print("freshness-corroboration: site_snapshot.json not found; run crawl-render-audit first", file=sys.stderr)
        return 2
    with open(snap_path, encoding="utf-8") as fh:
        snap = json.load(fh)

    pages = [p for p in snap.get("pages", []) if p.get("status") == 200 and p.get("features")]
    findings = []
    if not pages:
        _write(args.workdir, findings)
        print("freshness-corroboration: no readable pages in snapshot, 0 findings")
        return 0

    now_year = datetime.now(timezone.utc).year
    home = pages[0]
    host = snap.get("host", "")

    # ---- Freshness -----------------------------------------------------
    machine_dates = collect_jsonld_dates(pages)
    text_years = []
    for p in pages:
        text_years.extend(extract_years(p["features"].get("visible_text", "")))

    content_pages = [p for p in pages if re.search(r"/(blog|news|article|post|updates?)/", p["url"], re.I)]
    if not machine_dates and not text_years:
        findings.append(finding(
            "FC-01", "No publication or update dates found anywhere in the sample", "medium",
            "Across {} pages, no machine-readable dates (datePublished, dateModified, article meta tags) and no visible textual dates were detected. Retrieval systems cannot tell whether any fact is current.".format(len(pages)),
            "Stamp content pages with a visible last-updated date and mirror it in JSON-LD dateModified so machines can verify freshness.",
            effort="low"))
    else:
        newest = max([y for *_, y in machine_dates] + text_years, default=None)
        if newest is not None and (now_year - newest) * 12 >= STALE_MONTHS:
            findings.append(finding(
                "FC-02", "Newest detectable content date is stale", "high",
                "The most recent date signal found anywhere on the sampled pages is from {} (current year {}). Assistants asked for current facts will prefer sources that look maintained.".format(newest, now_year),
                "Refresh cornerstone pages, update their visible and structured dates, and publish something recent; stale sites lose citations to fresher competitors.",
                effort="medium"))
        if content_pages and not machine_dates:
            findings.append(finding(
                "FC-03", "Articles lack machine-readable dates", "medium",
                "{} blog/news-style pages were sampled but none expose datePublished or dateModified in JSON-LD or article meta tags.".format(len(content_pages)),
                "Add Article JSON-LD with datePublished and dateModified to every post template.",
                effort="low"))

    # Copyright year in footer text
    copy_years = []
    for m in re.finditer(r"(?:\u00a9|\(c\)|copyright)\s*(20\d{2})(?:\s*[-\u2013]\s*(20\d{2}))?",
                         home["features"].get("visible_text", ""), re.I):
        copy_years.append(int(m.group(2) or m.group(1)))
    if copy_years and max(copy_years) < now_year - 1:
        findings.append(finding(
            "FC-04", "Outdated copyright year in the footer", "low",
            "The homepage footer shows copyright {} while the current year is {}. A small but visible abandonment signal for both users and machines.".format(max(copy_years), now_year),
            "Render the copyright year dynamically so it always shows the current year.",
            effort="low"))

    # ---- Entity identity ----------------------------------------------
    all_types = set()
    for p in pages:
        all_types.update(p["features"].get("jsonld_types", []))
    has_org = any(t in all_types for t in ("Organization", "LocalBusiness", "Corporation", "OnlineStore", "WebSite"))
    if not has_org:
        findings.append(finding(
            "FC-05", "No Organization or WebSite identity markup", "high",
            "No page in the sample declares Organization, LocalBusiness, or WebSite JSON-LD. Machines have no authoritative statement of who this entity is, so brand facts stay fragmented and confusable with similarly named entities.",
            "Add a single Organization JSON-LD block on the homepage with name, legal name, url, logo, description, and sameAs links to official profiles.",
            effort="low"))

    same_as = []
    for p in pages:
        for item in p["features"].get("jsonld_items", []):
            sa = item.get("sameAs")
            if isinstance(sa, str):
                same_as.append(sa)
            elif isinstance(sa, list):
                same_as.extend(str(s) for s in sa)
    external_links = set()
    for p in pages:
        for href, _ in p["features"].get("links", []):
            for h in EXTERNAL_PROFILE_HOSTS:
                if h in href:
                    external_links.add(h)
    if not same_as and not external_links:
        findings.append(finding(
            "FC-06", "No links to independent profiles anywhere on the site", "medium",
            "The sample contains no sameAs declarations and no outbound links to independent profile hosts (Wikipedia, Wikidata, LinkedIn, GitHub, review platforms, social). Machines treat facts stated in only one place as weakly corroborated.",
            "Establish and interlink official profiles (LinkedIn, Wikidata, relevant directories and review platforms) and list them in the Organization sameAs array so machines can triangulate the same facts across independent sources.",
            effort="medium"))
    elif has_org and not same_as:
        findings.append(finding(
            "FC-07", "Organization markup exists but declares no sameAs profiles", "medium",
            "Organization/WebSite JSON-LD is present, yet the sameAs array is missing or empty even though external profiles are linked in page bodies ({}).".format(", ".join(sorted(external_links)) or "none detected"),
            "Add the official profile URLs to the Organization sameAs array; it is the strongest machine-readable disambiguation signal available.",
            effort="low"))

    # Brand ambiguity heuristic: short generic name and no descriptive framing
    site_name = home["features"].get("meta", {}).get("og:site_name") or ""
    title = home["features"].get("title", "")
    desc = home["features"].get("meta", {}).get("description", "")
    brand_token = (site_name or title.split("|")[0].split(" - ")[0]).strip()
    if brand_token and len(brand_token.split()) <= 2 and not desc and not has_org:
        findings.append(finding(
            "FC-08", "Brand entity is easy to confuse with same-named entities", "medium",
            "The site identifies itself only as '{}' with no meta description and no Organization markup. A short name with no category framing invites mistaken-identity answers when other entities share the name.".format(brand_token[:60]),
            "State the category explicitly everywhere the brand is named: title pattern 'Brand - what it is', a meta description that says what the brand does, and Organization JSON-LD with a description and disambiguating sameAs links.",
            effort="low"))

    # Name consistency across page titles
    if brand_token and len(brand_token) >= 3:
        with_brand = sum(1 for p in pages if brand_token.lower() in p["features"].get("title", "").lower())
        if len(pages) >= 4 and with_brand <= len(pages) // 2:
            findings.append(finding(
                "FC-09", "Brand name missing from most page titles", "low",
                "Only {}/{} sampled page titles contain the brand name '{}'. Consistent naming across pages is how machines associate content with the entity.".format(with_brand, len(pages), brand_token[:60]),
                "Adopt a consistent title pattern that ends with the brand name on every page.",
                effort="low"))

    # About and contact presence (trust and corroboration anchors)
    paths = " ".join(p["url"].lower() for p in pages)
    link_hrefs = " ".join(href.lower() for p in pages for href, _ in p["features"].get("links", []))
    if "about" not in paths and "/about" not in link_hrefs:
        findings.append(finding(
            "FC-10", "No discoverable About page", "medium",
            "Neither the sampled URLs nor any internal link points to an About page. Assistants asked 'who is {}' have no canonical self-description to quote.".format(host),
            "Publish an About page with a plain-text description of who the organization is, what it does, and for whom, written so a single paragraph can be quoted verbatim.",
            effort="low"))

    # ---- Answer engine optimization (AEO / GEO) ------------------------
    total_question_heads = sum(p["features"].get("question_headings", 0) for p in pages)
    if len(pages) >= 3 and total_question_heads == 0 and "FAQPage" not in all_types:
        findings.append(finding(
            "FC-11", "No answer-shaped content: zero question-form headings site-wide", "medium",
            "Across {} pages, not a single H2/H3 is phrased as a question and no FAQPage markup exists. Assistants match user questions against question-shaped headings and lift the paragraph beneath them; a site with none is structurally hard to quote.".format(len(pages)),
            "Rephrase key subheadings as the questions users actually ask (How much does X cost? How does Y work?) and answer each in the first sentence below it.",
            effort="low"))

    if not snap.get("llms_txt_present"):
        findings.append(finding(
            "FC-12", "No /llms.txt guide for AI crawlers", "low",
            "The site does not publish /llms.txt. It is an emerging convention that hands AI crawlers a curated map of the most quotable pages, shaping which content assistants read first.",
            "Publish /llms.txt at the site root: a short markdown file linking the pages that best define the brand, products, and key facts.",
            effort="low"))

    # Quotable brand definition (what a generative engine can lift verbatim)
    home_text = home["features"].get("visible_text", "")
    if brand_token and len(brand_token) >= 3 and len(home_text) > 300:
        linking = r"\b(is|are|helps|provides|offers|builds|makes|delivers|creates|specializes)\b"
        has_def_sentence = False
        for sentence in re.split(r"(?<=[.!?])\s+", home_text):
            s = sentence.strip()
            if (len(s) <= 220 and brand_token.lower() in s.lower()
                    and re.search(linking, s, re.I)):
                has_def_sentence = True
                break
        desc_defines = bool(desc) and brand_token.lower() in desc.lower() and len(desc) <= 250
        if not has_def_sentence and not desc_defines:
            findings.append(finding(
                "FC-13", "No quotable one-sentence brand definition", "medium",
                "Neither the homepage text nor the meta description contains a self-contained sentence (under about 220 characters) that names '{}' and states what it is or does. Generative engines compose answers from sentences they can lift cleanly; without one, they paraphrase, and paraphrases drift.".format(brand_token[:60]),
                "Write one plain sentence of the form 'Brand is a X that does Y for Z', place it in the first screen of the homepage and in the meta description, and reuse it verbatim in the Organization description.",
                effort="low"))

    # Schema coverage: markup exists but does not cover the content types present
    if all_types:
        article_types = {"Article", "BlogPosting", "NewsArticle"}
        product_types = {"Product", "Offer", "Service", "SoftwareApplication"}
        product_pages = [p for p in pages
                         if re.search(r"/(product|products|shop|store|pricing|plans)(/|$)", p["url"], re.I)
                         or p["features"].get("has_price_pattern")]
        gaps = []
        if content_pages and not (all_types & article_types):
            gaps.append("{} article-style page(s) with no Article/BlogPosting markup".format(len(content_pages)))
        if product_pages and not (all_types & product_types):
            gaps.append("{} product/pricing-style page(s) with no Product/Offer/Service markup".format(len(product_pages)))
        if gaps:
            findings.append(finding(
                "FC-14", "Structured data does not cover the content types the site actually has", "medium",
                "JSON-LD exists (types: {}) but coverage gaps remain: {}. Search and AI engines index articles and products correctly only when the matching schema type states what each page is.".format(", ".join(sorted(all_types))[:120], "; ".join(gaps)),
                "Extend the existing markup: Article JSON-LD with dates and author on post templates, Product/Offer JSON-LD with price and availability on product and pricing pages.",
                effort="medium"))

    # Thin corroboration: exactly one independent profile and no sameAs
    if not same_as and len(external_links) == 1:
        only = next(iter(external_links))
        findings.append(finding(
            "FC-15", "Corroboration rests on a single external profile", "low",
            "The only independent profile host linked from the site is {} and no sameAs declarations exist. One corroborating source is a thin base for machines that triangulate facts across independent references.".format(only),
            "Establish two or three additional official profiles (for example LinkedIn, Wikidata, a relevant directory), link them from the site, and list all of them in an Organization sameAs array.",
            effort="medium"))

    _write(args.workdir, findings)
    print("freshness-corroboration: {} findings".format(len(findings)))
    return 0


def _write(workdir, findings):
    with open(os.path.join(workdir, "freshness_findings.json"), "w", encoding="utf-8") as fh:
        json.dump({"skill": "freshness-corroboration", "findings": findings}, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sys.exit(main())
