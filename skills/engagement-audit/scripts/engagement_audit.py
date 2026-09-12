#!/usr/bin/env python3
"""
engagement_audit.py - On-site engagement and orientation audit.

Consumes the site_snapshot.json produced by the crawl-render-audit skill and
checks whether visitors who arrive can orient, scan, act, and get help.
Writes engagement_findings.json.

Usage:
  python3 engagement_audit.py --workdir ./audit_work
"""

import argparse
import json
import os
import re
import sys
import urllib.parse

CTA_VERBS = [
    "get started", "sign up", "signup", "start", "try", "buy", "shop", "order",
    "book", "subscribe", "download", "contact", "request", "join", "learn more",
    "get a quote", "demo", "enquire", "inquire", "donate", "apply", "register",
]


def finding(check, title, severity, evidence, action_summary, priority=None, effort="medium"):
    return {
        "check": check,
        "title": title,
        "severity": severity,
        "evidence": evidence,
        "suggested_action": {"summary": action_summary, "priority": priority or severity},
        "effort": effort,
        "source_skill": "engagement-audit",
    }


def words(text):
    return len(text.split())


def main():
    ap = argparse.ArgumentParser(description="On-site engagement audit")
    ap.add_argument("--workdir", default="./audit_work")
    args = ap.parse_args()

    snap_path = os.path.join(args.workdir, "site_snapshot.json")
    if not os.path.exists(snap_path):
        print("engagement-audit: site_snapshot.json not found; run crawl-render-audit first", file=sys.stderr)
        return 2
    with open(snap_path, encoding="utf-8") as fh:
        snap = json.load(fh)

    pages = [p for p in snap.get("pages", []) if p.get("status") == 200 and p.get("features")]
    findings = []
    if not pages:
        _write(args.workdir, findings)
        print("engagement-audit: no readable pages in snapshot, 0 findings")
        return 0

    home = pages[0]
    hf = home["features"]
    n = len(pages)

    # ---- Orientation ---------------------------------------------------
    if not hf["meta"].get("viewport"):
        findings.append(finding(
            "EN-01", "No viewport meta tag (mobile rendering broken)", "high",
            "The homepage lacks <meta name=\"viewport\">, so phones render the desktop layout zoomed out. Most first visits from AI answers and search happen on mobile, and an unreadable first screen is an immediate bounce.",
            "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> to every template and verify layouts reflow on small screens.",
            effort="low"))

    h1s = hf["headings"].get("h1", [])
    if not h1s:
        findings.append(finding(
            "EN-02", "Homepage has no H1 heading", "medium",
            "The homepage renders no h1 element, so neither visitors nor machines get a one-line statement of what this site is.",
            "Add a single descriptive H1 that states what the brand offers and for whom; use exactly one H1 per page.",
            effort="low"))
    elif len(h1s) > 3:
        findings.append(finding(
            "EN-03", "Multiple competing H1 headings on the homepage", "low",
            "The homepage contains {} h1 elements ({}). Multiple H1s dilute the page's one-line answer to 'what is this'.".format(len(h1s), "; ".join(h[:50] for h in h1s[:3])),
            "Keep one H1 per page and demote the rest to H2/H3.",
            effort="low"))

    no_nav = [p["url"] for p in pages if not p["features"]["has_nav"]]
    if len(no_nav) == n:
        findings.append(finding(
            "EN-04", "No navigation landmark on any sampled page", "medium",
            "0/{} pages contain a <nav> element. Visitors who land mid-site (as most AI-referred visitors do) have no persistent way to orient or move to related content.".format(n),
            "Wrap the primary menu in a <nav> element present on every page, with links to the handful of destinations that matter most.",
            effort="medium"))

    # ---- Scannability --------------------------------------------------
    long_para_pages = []
    for p in pages:
        lens = p["features"]["paragraph_lengths"]
        if lens:
            long_ratio = sum(1 for l in lens if l > 600) / len(lens)
            if long_ratio > 0.4 and sum(lens) > 2000:
                long_para_pages.append((p["url"], long_ratio))
    if long_para_pages:
        url, ratio = long_para_pages[0]
        findings.append(finding(
            "EN-05", "Wall-of-text pages with little visual structure", "medium",
            "On {} , {:.0f}% of paragraphs exceed 600 characters. Long unbroken prose is skimmed and abandoned by visitors, and key facts buried mid-paragraph are also harder for machines to extract.".format(url, ratio * 100),
            "Break long paragraphs at one idea each, add descriptive H2/H3 subheadings every few paragraphs, and convert enumerable facts into lists or tables.",
            effort="medium"))

    weak_heading_pages = []
    for p in pages:
        f = p["features"]
        total_words = words(f.get("visible_text", ""))
        subheads = len(f["headings"].get("h2", [])) + len(f["headings"].get("h3", []))
        if total_words > 800 and subheads == 0:
            weak_heading_pages.append(p["url"])
    if weak_heading_pages:
        findings.append(finding(
            "EN-06", "Long pages without any subheadings", "medium",
            "{} page(s) exceed 800 words with zero H2/H3 subheadings, e.g. {}. Nothing lets a reader (or an extractor) jump to the relevant section.".format(len(weak_heading_pages), weak_heading_pages[0]),
            "Add question-style H2 subheadings that name what each section answers; they double as anchors AI assistants can quote.",
            effort="low"))

    # ---- Action paths --------------------------------------------------
    action_texts = [t.lower() for t in hf.get("buttons", [])] + [t.lower() for _, t in hf.get("links", [])]
    has_cta = any(any(v in t for v in CTA_VERBS) for t in action_texts if t)
    if not has_cta:
        findings.append(finding(
            "EN-07", "No clear call to action on the homepage", "medium",
            "No homepage button or link text matches common action patterns (get started, contact, buy, book, sign up, demo). Visitors who are convinced still have nothing obvious to do next.",
            "Place one primary, verb-led call to action above the fold and repeat it at the end of the page; make the next step unmissable.",
            effort="low"))

    all_text = " ".join(p["features"].get("visible_text", "") for p in pages).lower()
    all_hrefs = " ".join(href.lower() for p in pages for href, _ in p["features"].get("links", []))
    has_email = bool(re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", all_text)) or "mailto:" in all_hrefs
    has_phone = bool(re.search(r"(?:\+?\d[\d\s().-]{7,}\d)", all_text)) or "tel:" in all_hrefs
    has_contact_link = "contact" in all_hrefs or "contact" in all_text[:4000]
    if not (has_email or has_phone or has_contact_link):
        findings.append(finding(
            "EN-08", "No visible way to contact the organization", "high",
            "Across {} sampled pages there is no email address, phone number, mailto/tel link, or contact link. Visitors with intent cannot convert, and machines cannot confirm the entity is reachable and real.".format(n),
            "Add a contact page linked from the main navigation and put at least one plain-text contact channel in the footer of every page.",
            effort="low"))

    # ---- Help and self-service ----------------------------------------
    all_types = set()
    for p in pages:
        all_types.update(p["features"].get("jsonld_types", []))
    faq_signal = ("faq" in all_hrefs or "faq" in all_text or "frequently asked" in all_text or "FAQPage" in all_types)
    if not faq_signal:
        findings.append(finding(
            "EN-09", "No FAQ or self-serve help content detected", "medium",
            "No FAQ link, 'frequently asked' section, or FAQPage markup appears anywhere in the sample. Repeat questions cost support effort on-site, and off-site they are exactly the question-shaped content AI assistants prefer to cite.",
            "Publish an FAQ answering the ten questions customers actually ask, in plain question-and-answer format, and mark it up with FAQPage JSON-LD.",
            effort="medium"))

    if n >= 5 and not any(p["features"]["has_search_input"] for p in pages):
        findings.append(finding(
            "EN-10", "No on-site search on a multi-page site", "low",
            "None of the {} sampled pages expose a search input. On sites with more than a handful of pages, visitors who cannot find something leave rather than browse.".format(n),
            "Add a simple site search (even a static index) reachable from the header.",
            effort="medium"))

    # ---- Continuity ----------------------------------------------------
    if n >= 3:
        weakly_linked = []
        base_host = snap.get("host", "").lower().lstrip("www.")
        for p in pages[1:]:
            internal = 0
            for href, _ in p["features"].get("links", []):
                if href.startswith("/") or base_host in href.lower():
                    internal += 1
            if internal < 3:
                weakly_linked.append(p["url"])
        if weakly_linked:
            findings.append(finding(
                "EN-11", "Dead-end pages with almost no internal links", "medium",
                "{} sampled page(s) contain fewer than 3 internal links, e.g. {}. A visitor who lands there from an AI answer has nowhere to go next, and crawlers treat weakly linked pages as unimportant.".format(len(weakly_linked), weakly_linked[0]),
                "Add related-content links and a persistent header/footer to every page so both visitors and crawlers can continue somewhere relevant.",
                effort="medium"))

    titles = [p["features"]["title"] for p in pages if p["features"]["title"]]
    if len(titles) >= 3 and len(set(titles)) < len(titles):
        dupes = [t for t in set(titles) if titles.count(t) > 1]
        findings.append(finding(
            "EN-12", "Duplicate titles across different pages", "medium",
            "{} distinct pages share identical titles (e.g. '{}'). In search results, AI citations, and browser tabs these pages are indistinguishable, so users cannot pick the right one.".format(titles.count(dupes[0]), dupes[0][:80]),
            "Write a unique, specific title per page that names its distinct topic.",
            effort="low"))

    breadcrumb = "BreadcrumbList" in all_types or "breadcrumb" in all_hrefs
    deep_pages = [p for p in pages if p["url"].rstrip("/").count("/") >= 4]
    if len(deep_pages) >= 2 and not breadcrumb:
        findings.append(finding(
            "EN-13", "No breadcrumbs on a site with deep pages", "low",
            "{} sampled pages sit two or more levels deep but no breadcrumb navigation or BreadcrumbList markup exists, so mid-site landers cannot see where they are.".format(len(deep_pages)),
            "Add breadcrumb navigation with BreadcrumbList JSON-LD on all pages below the top level.",
            effort="low"))

    # ---- Internal cross-linking depth (EN-14, EN-15) -------------------
    if n >= 4:
        def norm_path(u):
            return (urllib.parse.urlsplit(u).path or "/").rstrip("/").lower() or "/"

        interior = pages[1:]
        lateral_inbound = {norm_path(p["url"]): 0 for p in interior}
        for p in interior:
            own = norm_path(p["url"])
            for href, _ in p["features"].get("links", []):
                try:
                    target = norm_path(urllib.parse.urljoin(p["url"], href))
                except ValueError:
                    continue
                if target in lateral_inbound and target != own:
                    lateral_inbound[target] += 1
        spoke_only = [p["url"] for p in interior if lateral_inbound[norm_path(p["url"])] == 0]
        if len(spoke_only) >= 2 and len(spoke_only) >= (len(interior) + 1) // 2:
            findings.append(finding(
                "EN-14", "Hub-and-spoke linking: interior pages never link to each other", "medium",
                "{}/{} sampled interior pages receive no links from any other interior page; they are reachable only via the homepage (e.g. {}). A visitor reading one product or article is never guided to a related one, so sessions end after a single page.".format(len(spoke_only), len(interior), spoke_only[0]),
                "Add contextual related-content links between sibling pages (related products, next article, see also blocks) so every page hands the visitor a relevant next step.",
                effort="medium"))

    bh = snap.get("host", "").lower()
    bh = bh[4:] if bh.startswith("www.") else bh
    internal_anchor_texts = []
    for p in pages:
        for href, text in p["features"].get("links", []):
            t = (text or "").strip().lower()
            if t and (href.startswith("/") or href.startswith("#") or bh and bh in href.lower()):
                internal_anchor_texts.append(t)
    generic = {"click here", "here", "read more", "learn more", "more", "link", "this", "details", "view"}
    if len(internal_anchor_texts) >= 10:
        generic_count = sum(1 for t in internal_anchor_texts if t in generic)
        ratio = generic_count / len(internal_anchor_texts)
        if ratio > 0.3:
            findings.append(finding(
                "EN-15", "Generic anchor text on internal links", "low",
                "{:.0f}% of {} internal link anchors are generic ('read more', 'click here', 'learn more'). Descriptive anchors are how visitors decide where to go next and how machines infer what the target page is about; generic ones convey nothing to either.".format(ratio * 100, len(internal_anchor_texts)),
                "Rewrite link text to name the destination ('compare pricing plans', 'installation guide') instead of generic verbs.",
                effort="low"))

    # ---- Interactivity (EN-16) ----------------------------------------
    total_words_sample = sum(p["features"].get("word_count") or words(p["features"].get("visible_text", "")) for p in pages)
    if n >= 3 and total_words_sample >= 1500:
        interactive_elements = 0
        for p in pages:
            f = p["features"]
            interactive_elements += (f.get("forms", 0) + f.get("inputs_total", 0)
                                     + len(f.get("buttons", [])) + f.get("media_embeds", 0)
                                     + f.get("interactive_details", 0))
        if interactive_elements == 0:
            findings.append(finding(
                "EN-16", "Purely static text: no interactive elements anywhere", "medium",
                "Across {} pages and roughly {} words there is not a single form, input, button, video, embed, or disclosure widget. Static walls of text give visitors nothing to do, and dwell time and return visits track what a page lets people do, not just read.".format(n, total_words_sample),
                "Add at least one genuinely useful interactive element where it fits the content: a contact or signup form, a price or savings calculator, a product filter, an expandable FAQ, or a short demo video.",
                effort="medium"))

    _write(args.workdir, findings)
    print("engagement-audit: {} findings".format(len(findings)))
    return 0


def _write(workdir, findings):
    with open(os.path.join(workdir, "engagement_findings.json"), "w", encoding="utf-8") as fh:
        json.dump({"skill": "engagement-audit", "findings": findings}, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sys.exit(main())
