# Crawl and render checks (CR-01 to CR-27)

Each check: what fires it, severity, and the mechanism that makes it matter. All are agent-executable without the script: fetch raw HTML with curl and apply the same rules.

## Crawl layer: can a machine get in

- CR-01 (critical) robots.txt blocks all crawlers. Fires when `User-agent: *` is followed by `Disallow: /`, or when robots.txt disallows the audited entry URL. Mechanism: compliant crawlers and AI fetchers never read a single page; the site does not exist for them.
- CR-02 (high) robots.txt blocks AI crawlers by name. Fires when any of GPTBot, ChatGPT-User, ClaudeBot, Claude-Web, PerplexityBot, Google-Extended, Applebot-Extended, CCBot, anthropic-ai, cohere-ai, Meta-ExternalAgent, Bytespider, Amazonbot is disallowed site-wide while `*` is not. Mechanism: humans and Google still see the site, but the assistants themselves cannot read or cite it. Note: this can be a deliberate policy choice; the finding states the trade-off rather than assuming intent.
- CR-03 (critical) homepage unreachable. Non-200 status, TLS failure, or bot wall against a plain HTTP client. Mechanism: severed at step one. A detected certificate failure gets a tailored evidence string and fix (renew or repair the certificate) instead of generic server advice; the auditor never disables verification to continue, because to a real machine consumer the broken certificate IS the outage.
- CR-05 (high) plain HTTP only. Mechanism: downranking, browser warnings, some fetchers refuse.
- CR-06 (medium) redirect chains longer than 2 hops. Mechanism: crawl-budget waste and fetcher timeouts.
- CR-15 (medium) median raw-HTML latency over 3000 ms across the sample. Mechanism: real-time AI retrieval works on tight timeouts; slow origins get dropped from answers.
- CR-16 (medium) no sitemap via robots.txt directive or /sitemap.xml. Mechanism: discovery limited to link-following, deep pages may never be crawled.

## Render layer: can a machine read what humans see

- CR-04 (critical under 150 chars, high under 400) JavaScript render gap. Fires when a 200 page's raw HTML yields under 400 characters of visible text while loading 5+ scripts or mounting an SPA root container (root, app, __next, ___gatsby). Mechanism: many crawlers and most real-time AI fetchers read raw HTML only; the on-screen content literally is not in the document they receive. This is the single most common cause of a visible brand being invisible.
- CR-07 (high) zero JSON-LD across the whole sample. Mechanism: entity facts must be inferred from prose instead of read from schema.org statements; inference misses and mangles.
- CR-08 (high) JSON-LD present but unparseable. Mechanism: consumers ignore invalid blocks silently; the markup is decoration. Evidence includes the parser's message with line and column so the fix is a lookup, not a hunt.
- CR-11 (critical) noindex on sampled public pages, via the meta robots tag or the X-Robots-Tag response header (both are checked; sites set the header form just as often). Mechanism: explicit self-removal from every index.
- CR-09 (medium) missing titles; CR-10 (medium) meta description missing on more than half the sample; CR-12 (medium) no canonicals anywhere; CR-13 (medium) no lang attribute. Mechanism: each removes an explicit machine-readable statement and forces guessing (topic, summary, preferred URL, language).
- CR-14 (medium) over 50% of images missing alt across a sample with 5+ images. Mechanism: facts carried only in pixels (menus, price banners, infographics) are invisible to text extraction.

## Technical SEO layer: structure and semantics

- CR-17 (medium) no semantic content landmarks. Fires when 0/n sampled pages contain `<main>` or `<article>`. Mechanism: extractors cannot separate primary content from navigation, sidebars, and footers, which degrades what snippets and AI answers quote.
- CR-18 (low) broken heading hierarchy. Fires when, among pages with 3+ headings, a majority either start below h1 or skip levels downward (h1 straight to h3). Mechanism: the heading outline is how machines and assistive tech reconstruct document structure.
- CR-19 (low) no Open Graph or Twitter Card metadata on any page. Mechanism: links shared in chat and social render without preview, and some AI surfaces reuse og:description as the page summary.
- CR-20 (medium) low text-to-markup ratio. Fires when a majority of pages have over 30 KB of HTML, at least 400 chars of visible text, yet under 8% of bytes are text. Deliberately disjoint from CR-04 (which handles near-empty raw HTML): this catches real content buried in bloat. Mechanism: extraction budget spent on markup, worse summaries.
- CR-21 (low) title length hygiene. Fires when a majority of non-empty titles fall outside 15 to 70 characters. Mechanism: the title is the strongest ranking and citation field; too short wastes it, too long truncates.

## Keyword strategy and intent layer

Honest scope: search volume and keyword competition cannot be measured without third-party data, so these checks audit what IS visible on-page: whether the vocabulary a page targets in its title is the vocabulary the page actually uses, and whether repetition crosses from optimization into spam.

- CR-22 (medium) title/body intent mismatch. Eligible pages have 3+ significant title terms (4+ chars, non-stopword) and 200+ words of body. Fires when at least half of eligible pages match at most ONE title term in the body (typically just the brand name). Mechanism: rankers and answer engines match queries against title and body together; a page whose body never mentions what its title promises loses exactly the queries it targets.
- CR-23 (low) keyword stuffing. Fires when any page of 300+ words has a single non-stopword exceeding 6% of all words; evidence names the term and ratio. Mechanism: unnatural repetition trips spam heuristics and reads as low quality to summarizers.

## Performance and asset-loading layer

Measured with standard-library tools only: document byte size, fetch latency (CR-15 above), and HTML-declared asset hygiene. No headless browser is used, so these are raw-document signals, stated as such.

- CR-24 (low) very heavy HTML. Fires when the median sampled document exceeds 400 KB, or any page hits the 1.5 MB fetch cap. Mechanism: crawl budget, first-paint delay, and truncation by fetchers that stop reading.
- CR-25 (medium) render-blocking head scripts. Fires when a majority of pages load 6+ external scripts in `<head>` without defer/async. Mechanism: each blocks first paint, inflating bounce on the mobile visits AI referrals mostly produce.
- CR-26 (low) image loading hygiene. Fires when the sample holds 10+ images, over 70% lack width/height attributes, and none use loading="lazy". Mechanism: missing dimensions cause layout shift; eager-loading everything slows first meaningful paint.

## Deep-link citability

- CR-27 (medium) hash-based client routing. Fires when any sampled page carries 2+ links with href starting "#/" or "#!". Mechanism: URL fragments are never sent to the server, so assistants and search engines cannot cite, crawl, or deep-link those destinations; a shared link lands on the homepage state instead.

## Sampling rules (generalization by construction)

The page sample is chosen deterministically from homepage links: paths containing about, contact, product(s), pricing, services, blog, news, faq, docs, features, team, support are taken first, then shallowest paths, capped at max-pages. No hardcoded site knowledge; the same procedure applies to any vertical. Binary/asset URLs are excluded. Every fetch re-checks robots.txt.

## Politeness and safety

Honest user agent, GET only, 1.5 MB response cap, default 1 second delay between fetches, 150 second overall crawl budget, robots.txt honored per URL. Three extra probes total: robots.txt, sitemap (always fetched so lastmod freshness can be read), and llms.txt. The llms.txt probe carries soft-404 protection: an HTTP 200 answer only counts when the final URL still ends in /llms.txt and the body is not an HTML document, because many CMSs answer any missing path with a 200 HTML page. Fetches also detect forced gzip responses by magic bytes and decompress before decoding, so proxy-compressed pages cannot masquerade as empty ones.
