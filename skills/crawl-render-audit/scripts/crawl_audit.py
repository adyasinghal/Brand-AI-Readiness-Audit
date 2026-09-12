#!/usr/bin/env python3
"""
crawl_audit.py - Crawl and render-gap audit (standard library only).

Politely fetches a small, diverse sample of pages from a target site,
extracts machine-readable features from each page, runs the crawl-layer
and render-layer checks, and writes two artifacts:

  <workdir>/site_snapshot.json   shared page-feature cache for other skills
  <workdir>/crawl_findings.json  findings produced by this skill

Usage:
  python3 crawl_audit.py https://example.com --workdir ./audit_work
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from html.parser import HTMLParser

USER_AGENT = "BrandAuditBot/1.0 (read-only site audit; contact: hackathon submission)"
AI_CRAWLERS = ["GPTBot", "ClaudeBot", "Claude-Web", "PerplexityBot", "Google-Extended", "CCBot", "anthropic-ai", "Bytespider", "Amazonbot"]
DEFAULT_TIMEOUT = 8
MAX_HTML_BYTES = 1_500_000
GLOBAL_TIME_BUDGET = 150  # seconds for the whole crawl phase

PRIORITY_PATH_HINTS = [
    "about", "contact", "product", "products", "pricing", "services",
    "blog", "news", "faq", "docs", "features", "team", "support",
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with",
    "is", "are", "was", "were", "at", "by", "from", "as", "it", "its",
    "this", "that", "these", "those", "we", "our", "you", "your", "be",
    "been", "us", "not", "but", "all", "can", "will", "more", "has",
    "have", "had", "they", "their", "them", "his", "her", "she", "he",
    "into", "about", "than", "then", "when", "what", "which", "who",
    "how", "why", "there", "here", "also", "just", "only", "very",
    "over", "under", "out", "up", "down", "off", "so", "if", "no", "yes",
    "do", "does", "did", "get", "got", "make", "made", "use", "used",
    "one", "two", "new", "now", "any", "each", "other", "some", "such",
    "most", "many", "much", "own", "same", "both", "few", "per", "via",
    "home", "page", "site", "website", "welcome",
}


# ----------------------------------------------------------------------
# HTML feature extraction
# ----------------------------------------------------------------------

class FeatureParser(HTMLParser):
    """Single-pass extraction of the page features the audit checks need."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta = {}            # name/property -> content
        self.canonical = None
        self.lang = None
        self.headings = {"h1": [], "h2": [], "h3": []}
        self.links = []           # (href, anchor_text)
        self.images_total = 0
        self.images_missing_alt = 0
        self.script_count = 0
        self.script_bytes = 0
        self.jsonld_raw = []      # raw text of ld+json blocks
        self.has_nav = False
        self.has_noscript = False
        self.noscript_text = ""
        self.has_search_input = False
        self.forms = 0
        self.buttons = []         # button / submit text
        self.paragraphs = []      # visible <p> text lengths
        self.text_chunks = []
        self.root_div_ids = []    # ids of top-level-ish divs (SPA mount detection)
        self.heading_sequence = []       # document-order heading levels, e.g. [1, 2, 3, 2]
        self.landmarks = set()           # semantic landmarks seen: main, article, header, footer
        self.inputs_total = 0            # input + select + textarea elements
        self.media_embeds = 0            # video, audio, canvas, iframe elements
        self.interactive_details = 0     # details/summary disclosure widgets
        self.head_blocking_scripts = 0   # external scripts in <head> without defer/async
        self.images_missing_dims = 0     # img without both width and height attributes
        self.images_lazy = 0             # img with loading="lazy"
        self._in_head = False
        self._stack = []
        self._in_script = False
        self._script_type = ""
        self._script_buf = []
        self._in_style = False
        self._in_noscript = False
        self._in_title = False
        self._heading = None
        self._heading_buf = []
        self._in_p = False
        self._p_buf = []
        self._in_button = False
        self._button_buf = []
        self._link_href = None
        self._link_buf = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self._stack.append(tag)
        if tag == "script":
            self._in_script = True
            self._script_type = (a.get("type") or "").lower()
            self._script_buf = []
            self.script_count += 1
            if self._in_head and a.get("src") and "defer" not in a and "async" not in a and "module" not in self._script_type:
                self.head_blocking_scripts += 1
        elif tag == "head":
            self._in_head = True
        elif tag == "style":
            self._in_style = True
        elif tag == "noscript":
            self._in_noscript = True
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = a.get("name") or a.get("property")
            if key and "content" in a:
                self.meta[key.lower()] = a.get("content", "")
        elif tag == "link":
            if (a.get("rel") or "").lower() == "canonical":
                self.canonical = a.get("href")
        elif tag == "html":
            self.lang = a.get("lang")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if len(self.heading_sequence) < 200:
                self.heading_sequence.append(int(tag[1]))
            if tag in ("h1", "h2", "h3"):
                self._heading = tag
                self._heading_buf = []
        elif tag == "a":
            self._link_href = a.get("href")
            self._link_buf = []
        elif tag == "img":
            self.images_total += 1
            alt = a.get("alt")
            if alt is None or not alt.strip():
                self.images_missing_alt += 1
            if "width" not in a or "height" not in a:
                self.images_missing_dims += 1
            if (a.get("loading") or "").lower() == "lazy":
                self.images_lazy += 1
        elif tag == "nav":
            self.has_nav = True
        elif tag == "form":
            self.forms += 1
        elif tag in ("main", "article", "header", "footer"):
            self.landmarks.add(tag)
        elif tag in ("video", "audio", "canvas", "iframe"):
            self.media_embeds += 1
        elif tag == "details":
            self.interactive_details += 1
        elif tag in ("select", "textarea"):
            self.inputs_total += 1
        elif tag == "input":
            self.inputs_total += 1
            itype = (a.get("type") or "").lower()
            name = (a.get("name") or "").lower()
            if itype == "search" or "search" in name or "search" in (a.get("placeholder") or "").lower():
                self.has_search_input = True
            if itype == "submit" and a.get("value"):
                self.buttons.append(a.get("value"))
        elif tag == "button":
            self._in_button = True
            self._button_buf = []
        elif tag == "p":
            self._in_p = True
            self._p_buf = []
        elif tag == "div":
            div_id = (a.get("id") or "").lower()
            if div_id and len(self._stack) <= 3:
                self.root_div_ids.append(div_id)

    def handle_endtag(self, tag):
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
        if tag == "head":
            self._in_head = False
        if tag == "script":
            if self._in_script and "ld+json" in self._script_type:
                self.jsonld_raw.append("".join(self._script_buf))
            else:
                self.script_bytes += sum(len(s) for s in self._script_buf)
            self._in_script = False
            self._script_type = ""
        elif tag == "style":
            self._in_style = False
        elif tag == "noscript":
            self._in_noscript = False
        elif tag == "title":
            self._in_title = False
        elif tag in ("h1", "h2", "h3") and self._heading == tag:
            text = " ".join("".join(self._heading_buf).split())
            if text:
                self.headings[tag].append(text[:200])
            self._heading = None
        elif tag == "a":
            if self._link_href:
                text = " ".join("".join(self._link_buf).split())
                if len(self.links) < 800:
                    self.links.append((self._link_href, text[:120]))
            self._link_href = None
        elif tag == "button":
            text = " ".join("".join(self._button_buf).split())
            if text:
                self.buttons.append(text[:80])
            self._in_button = False
        elif tag == "p":
            text = " ".join("".join(self._p_buf).split())
            if text:
                self.paragraphs.append(len(text))
            self._in_p = False

    def handle_data(self, data):
        if self._in_script:
            self._script_buf.append(data)
            return
        if self._in_style:
            return
        if self._in_noscript:
            self.noscript_text += data[:500]
        if self._in_title:
            self.title += data
            return  # the <title> element is metadata, not visible body text
        if self._heading:
            self._heading_buf.append(data)
        if self._in_p:
            self._p_buf.append(data)
        if self._in_button:
            self._button_buf.append(data)
        if self._link_href is not None:
            self._link_buf.append(data)
        stripped = data.strip()
        if stripped:
            self.text_chunks.append(stripped)


def extract_features(url, html):
    parser = FeatureParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass  # keep whatever was extracted before the parse error

    visible_text = " ".join(parser.text_chunks)

    # Keyword statistics for intent and stuffing checks
    word_tokens = re.findall(r"[a-z][a-z0-9'-]+", visible_text.lower())
    word_count = len(word_tokens)
    top_term, top_term_ratio = "", 0.0
    if word_count >= 50:
        freq = {}
        for w in word_tokens:
            if w in STOPWORDS or len(w) < 4:
                continue
            freq[w] = freq.get(w, 0) + 1
        if freq:
            top_term = max(freq, key=lambda k: (freq[k], k))
            top_term_ratio = freq[top_term] / word_count

    # Does the title's vocabulary actually appear in the body (intent alignment)
    title_clean = " ".join(parser.title.split()).lower()
    sig_terms = sorted({w for w in re.findall(r"[a-z0-9'-]{4,}", title_clean) if w not in STOPWORDS})
    body_lower = visible_text.lower()
    title_terms_matched = sum(1 for t in sig_terms if t in body_lower)

    # Question-form subheadings (answer-shaped content for AEO)
    question_words = ("how", "what", "why", "when", "where", "who", "can",
                      "does", "do", "is", "are", "should", "which")
    question_headings = 0
    for lvl in ("h2", "h3"):
        for h in parser.headings.get(lvl, []):
            hl = h.strip().lower()
            first = hl.split()[0] if hl.split() else ""
            if hl.endswith("?") or first in question_words:
                question_headings += 1

    has_price_pattern = bool(re.search(
        r"(?:[$\u20ac\u00a3\u20b9]\s?\d|\b(?:USD|EUR|INR|GBP)\s?\d|\bRs\.?\s?\d)", visible_text))

    jsonld_parsed, jsonld_errors = [], 0
    for raw in parser.jsonld_raw:
        try:
            data = json.loads(raw.strip())
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict):
                    graph = item.get("@graph")
                    if isinstance(graph, list):
                        jsonld_parsed.extend(g for g in graph if isinstance(g, dict))
                    else:
                        jsonld_parsed.append(item)
        except (json.JSONDecodeError, ValueError):
            jsonld_errors += 1

    return {
        "url": url,
        "title": " ".join(parser.title.split())[:300],
        "meta": parser.meta,
        "canonical": parser.canonical,
        "lang": parser.lang,
        "headings": parser.headings,
        "links": parser.links[:800],
        "images_total": parser.images_total,
        "images_missing_alt": parser.images_missing_alt,
        "script_count": parser.script_count,
        "script_bytes": parser.script_bytes,
        "jsonld_types": sorted({str(i.get("@type")) for i in jsonld_parsed if i.get("@type")}),
        "jsonld_items": jsonld_parsed[:40],
        "jsonld_parse_errors": jsonld_errors,
        "has_nav": parser.has_nav,
        "has_noscript": parser.has_noscript,
        "noscript_text": " ".join(parser.noscript_text.split())[:300],
        "has_search_input": parser.has_search_input,
        "forms": parser.forms,
        "buttons": parser.buttons[:60],
        "paragraph_lengths": parser.paragraphs[:400],
        "root_div_ids": parser.root_div_ids[:10],
        "visible_text": visible_text[:60000],
        "text_len": len(visible_text),
        "html_bytes": len(html),
        "word_count": word_count,
        "top_term": top_term,
        "top_term_ratio": round(top_term_ratio, 4),
        "title_sig_terms": len(sig_terms),
        "title_terms_matched": title_terms_matched,
        "question_headings": question_headings,
        "has_price_pattern": has_price_pattern,
        "heading_sequence": parser.heading_sequence[:200],
        "landmarks": sorted(parser.landmarks),
        "inputs_total": parser.inputs_total,
        "media_embeds": parser.media_embeds,
        "interactive_details": parser.interactive_details,
        "head_blocking_scripts": parser.head_blocking_scripts,
        "images_missing_dims": parser.images_missing_dims,
        "images_lazy": parser.images_lazy,
        "og_present": any(k.startswith("og:") for k in parser.meta),
        "twitter_present": any(k.startswith("twitter:") for k in parser.meta),
    }


# ----------------------------------------------------------------------
# Fetching
# ----------------------------------------------------------------------

class RedirectRecorder(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        self.chain = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.chain.append({"status": code, "to": newurl})
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, timeout=DEFAULT_TIMEOUT, binary_ok=False):
    """Fetch a URL. Returns dict with status, final_url, redirects, body, elapsed_ms, error."""
    recorder = RedirectRecorder()
    opener = urllib.request.build_opener(recorder)
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en",
    })
    start = time.monotonic()
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read(MAX_HTML_BYTES)
            elapsed = int((time.monotonic() - start) * 1000)
            charset = resp.headers.get_content_charset() or "utf-8"
            if binary_ok:
                body = raw
            else:
                body = raw.decode(charset, errors="replace")
            return {
                "status": resp.status,
                "final_url": resp.geturl(),
                "redirects": recorder.chain,
                "content_type": resp.headers.get("Content-Type", ""),
                "body": body,
                "elapsed_ms": elapsed,
                "error": None,
            }
    except urllib.error.HTTPError as e:
        return {"status": e.code, "final_url": url, "redirects": recorder.chain,
                "content_type": "", "body": "", "elapsed_ms": int((time.monotonic() - start) * 1000),
                "error": "HTTP {}".format(e.code)}
    except Exception as e:
        return {"status": None, "final_url": url, "redirects": recorder.chain,
                "content_type": "", "body": "", "elapsed_ms": int((time.monotonic() - start) * 1000),
                "error": "{}: {}".format(type(e).__name__, e)}


def normalize_start_url(raw):
    raw = raw.strip()
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    return raw


def same_site(base_host, href_url):
    host = urllib.parse.urlsplit(href_url).netloc.lower()
    base = base_host.lower()
    return host == base or host == "www." + base or base == "www." + host


def pick_pages(base_url, links, max_pages):
    """Deterministically choose a diverse set of internal pages to sample."""
    base_host = urllib.parse.urlsplit(base_url).netloc
    seen, scored = set(), []
    for href, _text in links:
        try:
            absolute = urllib.parse.urljoin(base_url, href)
        except ValueError:
            continue
        split = urllib.parse.urlsplit(absolute)
        if split.scheme not in ("http", "https") or not same_site(base_host, absolute):
            continue
        path_norm = re.sub(r"/index\.(html?|php)$", "/", split.path or "/", flags=re.I)
        clean = urllib.parse.urlunsplit((split.scheme, split.netloc, path_norm or "/", "", ""))
        if clean.rstrip("/") == base_url.rstrip("/") or clean in seen:
            continue
        path = (split.path or "/").lower()
        if re.search(r"\.(pdf|jpg|jpeg|png|gif|svg|webp|zip|mp4|css|js|ico|xml)$", path):
            continue
        seen.add(clean)
        hint = min((i for i, h in enumerate(PRIORITY_PATH_HINTS) if h in path), default=len(PRIORITY_PATH_HINTS))
        depth = path.count("/")
        scored.append((hint, depth, clean))
    scored.sort()
    return [u for _, _, u in scored[: max_pages - 1]]


# ----------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------

def finding(check, title, severity, evidence, action_summary, priority=None, effort="medium"):
    return {
        "check": check,
        "title": title,
        "severity": severity,
        "evidence": evidence,
        "suggested_action": {"summary": action_summary, "priority": priority or severity},
        "effort": effort,
        "source_skill": "crawl-render-audit",
    }


def analyze_robots(robots_body, robots_status):
    """Return (findings, parser, ai_block_info, sitemaps)."""
    findings, sitemaps, ai_blocked = [], [], []
    rp = urllib.robotparser.RobotFileParser()
    if robots_status == 200 and robots_body:
        rp.parse(robots_body.splitlines())
        current_agents = []
        for line in robots_body.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            m = re.match(r"(?i)user-agent\s*:\s*(.+)", line)
            if m:
                current_agents = [m.group(1).strip()]
                continue
            m = re.match(r"(?i)sitemap\s*:\s*(\S+)", line)
            if m:
                sitemaps.append(m.group(1))
                continue
            m = re.match(r"(?i)disallow\s*:\s*(\S*)", line)
            if m and m.group(1) == "/":
                for agent in current_agents:
                    if agent == "*":
                        findings.append(finding(
                            "CR-01", "robots.txt blocks all crawlers site-wide", "critical",
                            "robots.txt contains 'User-agent: *' followed by 'Disallow: /', which excludes every compliant crawler including AI assistants.",
                            "Remove or narrow the blanket 'Disallow: /' rule so compliant crawlers can index public content; keep disallow rules only for private paths.",
                            effort="low"))
                    else:
                        for bot in AI_CRAWLERS:
                            if bot.lower() in agent.lower():
                                ai_blocked.append(bot)
        ai_blocked = sorted(set(ai_blocked))
        if ai_blocked and not any(f["check"] == "CR-01" for f in findings):
            findings.append(finding(
                "CR-02", "robots.txt blocks AI assistant crawlers", "high",
                "robots.txt disallows these AI-associated user agents from the whole site: {}. Pages remain visible to humans but AI assistants that respect robots.txt cannot read or cite them.".format(", ".join(ai_blocked)),
                "If AI visibility is a goal, remove site-wide Disallow rules for AI crawlers ({}), or scope them to genuinely private paths only.".format(", ".join(ai_blocked)),
                effort="low"))
    else:
        rp.parse([])  # no robots file: everything allowed
    return findings, rp, ai_blocked, sitemaps


def run_page_checks(pages, base_url, extras):
    """Corpus-level checks over the fetched page sample."""
    out = []
    ok_pages = [p for p in pages if p["status"] == 200 and p["features"]]
    n = len(ok_pages)

    home = pages[0] if pages else None
    if home is not None and home.get("robots_blocked"):
        return out  # CR-01 already explains why nothing else could run
    if home is None or home["status"] != 200:
        status = home["status"] if home else "no response"
        err = (home or {}).get("error") or ""
        out.append(finding(
            "CR-03", "Homepage is not reachable with a plain HTTP fetch", "critical",
            "GET {} returned status {} {}. A crawler that cannot load the homepage cannot discover or cite anything on the site.".format(base_url, status, err).strip(),
            "Ensure the homepage returns HTTP 200 to standard crawler user agents; fix server errors, bot walls, or TLS problems that break non-browser clients.",
            effort="high"))
        return out
    if not n:
        return out

    # Render gap: little visible text plus SPA markers
    for p in ok_pages:
        f = p["features"]
        spa_mount = any(i in ("root", "app", "__next", "___gatsby", "app-root") for i in f["root_div_ids"])
        if f["text_len"] < 400 and (f["script_count"] >= 5 or spa_mount):
            sev = "critical" if f["text_len"] < 150 else "high"
            out.append(finding(
                "CR-04", "Content appears to require JavaScript rendering (render gap)", sev,
                "{} serves only {} characters of visible text in raw HTML while loading {} scripts{}. Crawlers and AI fetchers that read raw HTML see an effectively empty page.".format(
                    p["url"], f["text_len"], f["script_count"],
                    " and mounts an SPA root container" if spa_mount else ""),
                "Serve the primary content in the initial HTML: enable server-side rendering, static generation, or prerendering so key facts exist as plain text before any JavaScript runs.",
                effort="high"))
            break  # one corpus-level finding with the strongest example

    # HTTPS
    if urllib.parse.urlsplit(home["final_url"] or base_url).scheme == "http":
        out.append(finding(
            "CR-05", "Site is served over plain HTTP", "high",
            "The homepage resolves to {} without HTTPS. Many crawlers and browsers downrank or warn on non-HTTPS sites.".format(home["final_url"]),
            "Install TLS and redirect all HTTP traffic to HTTPS with a single 301 redirect.",
            effort="medium"))

    # Redirect chains
    long_chains = [p for p in pages if len(p.get("redirects", [])) > 2]
    if long_chains:
        worst = max(long_chains, key=lambda p: len(p["redirects"]))
        out.append(finding(
            "CR-06", "Long redirect chains before content is served", "medium",
            "{} passes through {} redirects before returning content. Each hop costs crawl budget and increases the chance a fetcher gives up.".format(worst["url"], len(worst["redirects"])),
            "Collapse redirect chains so every URL reaches its final destination in at most one hop.",
            effort="low"))

    # Structured data
    pages_with_jsonld = [p for p in ok_pages if p["features"]["jsonld_types"]]
    if not pages_with_jsonld:
        out.append(finding(
            "CR-07", "No JSON-LD structured data on any sampled page", "high",
            "Crawled {} pages; 0/{} contain a script[type=application/ld+json] block. Without schema.org markup, machines must guess entity facts from prose.".format(n, n),
            "Add JSON-LD to key templates: Organization or WebSite on the homepage, and Product, Service, Article, or FAQPage types on the matching page types.",
            effort="medium"))
    parse_errors = sum(p["features"]["jsonld_parse_errors"] for p in ok_pages)
    if parse_errors:
        bad = [p["url"] for p in ok_pages if p["features"]["jsonld_parse_errors"]][:3]
        out.append(finding(
            "CR-08", "Invalid JSON-LD blocks that fail to parse", "high",
            "{} JSON-LD block(s) across the sample are not valid JSON (for example on {}). Invalid blocks are silently ignored by consumers, so the markup delivers no value.".format(parse_errors, ", ".join(bad)),
            "Fix the JSON syntax errors (trailing commas, unescaped quotes, comments) and validate with the schema.org validator before deploying.",
            effort="low"))

    # Titles and descriptions
    missing_title = [p["url"] for p in ok_pages if not p["features"]["title"]]
    if missing_title:
        out.append(finding(
            "CR-09", "Pages missing a <title> element", "medium",
            "{}/{} sampled pages have an empty or missing title, e.g. {}.".format(len(missing_title), n, missing_title[0]),
            "Give every page a unique, descriptive title that names the brand and the page topic.",
            effort="low"))
    missing_desc = [p["url"] for p in ok_pages if not p["features"]["meta"].get("description")]
    if len(missing_desc) > n // 2:
        out.append(finding(
            "CR-10", "Meta descriptions missing on most pages", "medium",
            "{}/{} sampled pages lack a meta description, e.g. {}. Search and AI surfaces then improvise the summary, often badly.".format(len(missing_desc), n, missing_desc[0]),
            "Write a one-to-two sentence meta description per page that states plainly what the page offers.",
            effort="low"))

    # noindex
    noindexed = [p["url"] for p in ok_pages if "noindex" in (p["features"]["meta"].get("robots", "")).lower()]
    if noindexed:
        out.append(finding(
            "CR-11", "Public pages carry a meta robots noindex directive", "critical",
            "These sampled pages ask crawlers not to index them: {}. They are invisible to search and AI retrieval by explicit instruction.".format(", ".join(noindexed[:4])),
            "Remove the noindex directive from pages that should be discoverable; keep it only on genuinely private or duplicate pages.",
            effort="low"))

    # Canonical and lang
    if sum(1 for p in ok_pages if not p["features"]["canonical"]) == n:
        out.append(finding(
            "CR-12", "No canonical URLs declared", "medium",
            "0/{} sampled pages declare rel=canonical. Parameter and duplicate URLs can then split ranking and citation signals.".format(n),
            "Add a rel=canonical link on every page pointing to its preferred URL.",
            effort="low"))
    if not home["features"]["lang"]:
        out.append(finding(
            "CR-13", "Missing lang attribute on <html>", "medium",
            "The homepage <html> element has no lang attribute, so language detection is left to guesswork for crawlers and screen readers.",
            "Set the lang attribute (for example lang=\"en\") on the html element of every template.",
            effort="low"))

    # Alt text
    total_img = sum(p["features"]["images_total"] for p in ok_pages)
    missing_alt = sum(p["features"]["images_missing_alt"] for p in ok_pages)
    if total_img >= 5 and missing_alt / total_img > 0.5:
        out.append(finding(
            "CR-14", "Most images have no alt text", "medium",
            "{}/{} images across the sample lack alt text. Facts carried only in images (banners, infographics, menus) are invisible to text-based extraction.".format(missing_alt, total_img),
            "Add descriptive alt text to informative images and restate any image-only facts (prices, hours, claims) as plain HTML text.",
            effort="medium"))

    # Latency
    times = sorted(p["elapsed_ms"] for p in ok_pages)
    median = times[len(times) // 2]
    if median > 3000:
        out.append(finding(
            "CR-15", "Slow server responses", "medium",
            "Median raw-HTML fetch time across {} pages was {} ms. Slow responses shrink crawl coverage and time out real-time AI fetchers.".format(n, median),
            "Cache HTML at the edge or tune the server so uncached HTML responds in under one second.",
            effort="high"))

    # Sitemap
    if not extras.get("sitemap_found"):
        out.append(finding(
            "CR-16", "No XML sitemap discovered", "medium",
            "No Sitemap directive in robots.txt and {} returned status {}. Crawlers must rely purely on link discovery, so deep pages may never be found.".format(extras.get("sitemap_url", "/sitemap.xml"), extras.get("sitemap_status")),
            "Publish an XML sitemap listing canonical URLs and reference it from robots.txt.",
            effort="low"))

    # ---- Technical SEO: structure and semantics (CR-17 to CR-21) -------
    def feat(p, key, default):
        return p["features"].get(key, default)

    if not any(("main" in feat(p, "landmarks", [])) or ("article" in feat(p, "landmarks", [])) for p in ok_pages):
        out.append(finding(
            "CR-17", "No semantic content landmarks (main or article) on any page", "medium",
            "0/{} sampled pages wrap their primary content in <main> or <article>. Extractors cannot cleanly separate the content that matters from navigation, sidebars, and footers, which degrades what search snippets and AI answers quote.".format(n),
            "Wrap the primary content of every template in <main> (and articles in <article>); keep navigation and boilerplate outside it.",
            effort="low"))

    broken_hierarchy = []
    for p in ok_pages:
        seq = feat(p, "heading_sequence", [])
        if len(seq) >= 3:
            skips = (seq[0] > 1) or any(b - a > 1 for a, b in zip(seq, seq[1:]) if b > a)
            if skips:
                broken_hierarchy.append(p["url"])
    eligible_h = [p for p in ok_pages if len(feat(p, "heading_sequence", [])) >= 3]
    if eligible_h and len(broken_hierarchy) > len(eligible_h) // 2:
        out.append(finding(
            "CR-18", "Heading hierarchy skips levels on most pages", "low",
            "{}/{} pages with 3+ headings either start below h1 or jump levels (for example h1 straight to h3), e.g. {}. A coherent outline is how machines and assistive tech reconstruct document structure.".format(len(broken_hierarchy), len(eligible_h), broken_hierarchy[0]),
            "Nest headings strictly (h1, then h2, then h3) so each page produces a clean outline.",
            effort="low"))

    if not any(feat(p, "og_present", False) or feat(p, "twitter_present", False) for p in ok_pages):
        out.append(finding(
            "CR-19", "No Open Graph or Twitter Card metadata anywhere", "low",
            "0/{} sampled pages declare og: or twitter: meta tags. Links shared in chat apps and social feeds render without a title, description, or image, and some AI surfaces reuse og:description as the page summary.".format(n),
            "Add og:title, og:description, and og:image to every template (Twitter Cards can mirror the same values).",
            effort="low"))

    bloated = [p for p in ok_pages
               if feat(p, "html_bytes", 0) > 30000
               and p["features"]["text_len"] >= 400
               and p["features"]["text_len"] / feat(p, "html_bytes", 1) < 0.08]
    if bloated and len(bloated) > n // 2:
        worst = min(bloated, key=lambda p: p["features"]["text_len"] / feat(p, "html_bytes", 1))
        ratio = worst["features"]["text_len"] / feat(worst, "html_bytes", 1)
        out.append(finding(
            "CR-20", "Low text-to-markup ratio (content buried in markup)", "medium",
            "On {}/{} pages under 8% of the HTML bytes are visible text (worst: {} at {:.1f}%). Extractors spend their budget parsing markup instead of reading content, and boilerplate-heavy pages summarize worse.".format(len(bloated), n, worst["url"], ratio * 100),
            "Trim inlined SVG/CSS/JS and boilerplate from templates so the primary text is a meaningful share of the document.",
            effort="medium"))

    titled = [p for p in ok_pages if p["features"]["title"]]
    bad_len = [p for p in titled if not (15 <= len(p["features"]["title"]) <= 70)]
    if titled and len(bad_len) > len(titled) // 2:
        example = bad_len[0]
        out.append(finding(
            "CR-21", "Page titles outside the useful length range on most pages", "low",
            "{}/{} titles fall outside 15 to 70 characters (e.g. '{}' at {} chars). Too-short titles waste the strongest ranking and citation field; too-long titles get truncated in results.".format(len(bad_len), len(titled), example["features"]["title"][:60], len(example["features"]["title"])),
            "Rewrite titles to roughly 15 to 70 characters that state the page topic and end with the brand name.",
            effort="low"))

    # ---- Keyword strategy and intent (CR-22, CR-23) ---------------------
    eligible_kw = [p for p in ok_pages
                   if feat(p, "title_sig_terms", 0) >= 3 and feat(p, "word_count", 0) >= 200]
    mismatch = [p for p in eligible_kw if feat(p, "title_terms_matched", 99) <= 1]
    if eligible_kw and len(mismatch) >= (len(eligible_kw) + 1) // 2:
        out.append(finding(
            "CR-22", "Page titles promise topics the body text never mentions", "medium",
            "On {}/{} content pages, at most one significant word from the title (typically just the brand name) appears anywhere in the body (e.g. {}). Rankers and answer engines match queries against title and body together; a mismatch reads as bait or misclassification and costs the page the very queries it targets.".format(len(mismatch), len(eligible_kw), mismatch[0]["url"]),
            "Align each title with the page's actual vocabulary: use the words users search for in both the title and naturally throughout the body.",
            effort="medium"))

    stuffed = [p for p in ok_pages if feat(p, "word_count", 0) >= 300 and feat(p, "top_term_ratio", 0) > 0.06]
    if stuffed:
        worst = max(stuffed, key=lambda p: feat(p, "top_term_ratio", 0))
        out.append(finding(
            "CR-23", "Keyword stuffing detected", "low",
            "On {} the single term '{}' makes up {:.1f}% of all words. Unnatural repetition triggers spam heuristics in rankers and reads as low-quality to humans and AI summarizers alike.".format(worst["url"], feat(worst, "top_term", ""), feat(worst, "top_term_ratio", 0) * 100),
            "Rewrite the page in natural language; cover the topic with related terms and synonyms instead of repeating one keyword.",
            effort="low"))

    # ---- Performance and asset loading (CR-24 to CR-26) -----------------
    sizes = sorted(feat(p, "html_bytes", 0) for p in ok_pages)
    if sizes:
        median_size = sizes[len(sizes) // 2]
        capped = [p for p in ok_pages if feat(p, "html_bytes", 0) >= MAX_HTML_BYTES]
        if median_size > 400_000 or capped:
            detail = "median HTML document is {} KB".format(median_size // 1024)
            if capped:
                detail += "; {} page(s) exceed the {} KB fetch cap entirely".format(len(capped), MAX_HTML_BYTES // 1024)
            out.append(finding(
                "CR-24", "Very heavy HTML documents", "low",
                "Across {} pages the {}. Oversized documents burn crawl budget, slow first paint, and some fetchers truncate them, losing whatever content sits at the bottom.".format(n, detail),
                "Move inlined assets to cached external files and paginate extremely long pages so HTML stays lean.",
                effort="medium"))

    blocking = [p for p in ok_pages if feat(p, "head_blocking_scripts", 0) >= 6]
    if blocking and len(blocking) > n // 2:
        worst = max(blocking, key=lambda p: feat(p, "head_blocking_scripts", 0))
        out.append(finding(
            "CR-25", "Many render-blocking scripts in the document head", "medium",
            "{}/{} pages load 6+ external scripts in <head> without defer or async (worst: {} with {}). Every one delays first paint, which inflates bounce on the mobile visits AI referrals mostly produce.".format(len(blocking), n, worst["url"], feat(worst, "head_blocking_scripts", 0)),
            "Add defer (or async) to non-critical scripts and move them out of <head> so content renders before JavaScript loads.",
            effort="low"))

    total_dims_missing = sum(feat(p, "images_missing_dims", 0) for p in ok_pages)
    total_lazy = sum(feat(p, "images_lazy", 0) for p in ok_pages)
    if total_img >= 10 and total_dims_missing / total_img > 0.7 and total_lazy == 0:
        out.append(finding(
            "CR-26", "Images ship without dimensions or lazy loading", "low",
            "{}/{} images across the sample lack width/height attributes and none use loading=\"lazy\". Missing dimensions cause layout shift while loading; eager-loading every image slows the first meaningful paint.".format(total_dims_missing, total_img),
            "Add width and height attributes to images and loading=\"lazy\" to below-the-fold images.",
            effort="low"))

    return out


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Crawl and render-gap audit")
    ap.add_argument("url")
    ap.add_argument("--workdir", default="./audit_work")
    ap.add_argument("--max-pages", type=int, default=8)
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args()

    os.makedirs(args.workdir, exist_ok=True)
    base_url = normalize_start_url(args.url)
    started = time.monotonic()
    findings = []

    # robots.txt
    parts = urllib.parse.urlsplit(base_url)
    origin = "{}://{}".format(parts.scheme, parts.netloc)
    robots = fetch(origin + "/robots.txt")
    robots_findings, rp, ai_blocked, sitemaps = analyze_robots(robots.get("body") or "", robots.get("status"))
    findings.extend(robots_findings)

    def allowed(u):
        try:
            return rp.can_fetch(USER_AGENT, u) and rp.can_fetch("*", u)
        except Exception:
            return True

    # sitemap probe
    sitemap_url = sitemaps[0] if sitemaps else origin + "/sitemap.xml"
    sitemap_found, sitemap_status = bool(sitemaps), None
    if not sitemap_found:
        sm = fetch(sitemap_url)
        sitemap_status = sm["status"]
        sitemap_found = sm["status"] == 200 and ("<urlset" in sm["body"] or "<sitemapindex" in sm["body"])

    # llms.txt probe (used by the orchestrator for proactive suggestions)
    llms = fetch(origin + "/llms.txt")
    llms_present = llms["status"] == 200 and len(llms["body"].strip()) > 0

    pages = []

    def fetch_page(url):
        if not allowed(url):
            return {"url": url, "status": None, "final_url": url, "redirects": [],
                    "elapsed_ms": 0, "error": "blocked by robots.txt", "features": None,
                    "robots_blocked": True}
        r = fetch(url)
        feats = None
        if r["status"] == 200 and "html" in (r["content_type"] or "text/html"):
            feats = extract_features(url, r["body"])
        return {"url": url, "status": r["status"], "final_url": r["final_url"],
                "redirects": r["redirects"], "elapsed_ms": r["elapsed_ms"],
                "error": r["error"], "features": feats, "robots_blocked": False}

    home = fetch_page(base_url)
    if home.get("robots_blocked"):
        # CR-01 already recorded if blanket; make it explicit either way
        if not any(f["check"] == "CR-01" for f in findings):
            findings.append(finding(
                "CR-01", "robots.txt blocks the audited entry URL", "critical",
                "robots.txt disallows fetching {} for compliant crawlers, so the audit stopped after the robots check.".format(base_url),
                "Allow public pages in robots.txt; blanket disallow rules make the site invisible to every compliant crawler and AI assistant.",
                effort="low"))
    pages.append(home)

    if home["status"] == 200 and home["features"]:
        for url in pick_pages(home["final_url"] or base_url, home["features"]["links"], args.max_pages):
            if time.monotonic() - started > GLOBAL_TIME_BUDGET:
                break
            time.sleep(args.delay)
            pages.append(fetch_page(url))

    findings.extend(run_page_checks(pages, base_url, {
        "sitemap_found": sitemap_found, "sitemap_status": sitemap_status, "sitemap_url": sitemap_url,
    }))

    snapshot = {
        "base_url": base_url,
        "host": parts.netloc,
        "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "robots": {"status": robots.get("status"), "ai_crawlers_blocked": ai_blocked,
                   "sitemaps_declared": sitemaps},
        "sitemap_found": sitemap_found,
        "llms_txt_present": llms_present,
        "pages": pages,
    }
    with open(os.path.join(args.workdir, "site_snapshot.json"), "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, ensure_ascii=False)
    with open(os.path.join(args.workdir, "crawl_findings.json"), "w", encoding="utf-8") as fh:
        json.dump({"skill": "crawl-render-audit", "findings": findings}, fh, ensure_ascii=False, indent=2)

    print("crawl-render-audit: fetched {} pages, {} findings".format(len(pages), len(findings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
