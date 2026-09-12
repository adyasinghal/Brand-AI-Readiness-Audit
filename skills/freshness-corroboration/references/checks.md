# Freshness, corroboration, and identity checks (FC-01 to FC-16)

## Freshness: do the facts look current

- FC-01 (medium) no date signal anywhere. Fires when the whole sample yields zero machine-readable dates (JSON-LD datePublished/dateModified, article:published_time meta) and zero visible textual dates. Mechanism: retrieval systems prefer sources whose currency they can verify; undated facts are risky to repeat.
- FC-02 (high) newest detectable date is 18+ months old. Mechanism: for time-sensitive queries, assistants and rankers systematically prefer fresher corroborating sources; a stale-looking site loses citations even when its facts are still true. Threshold rationale: 18 months separates "not updated this quarter" from "plausibly abandoned" across most verticals without punishing evergreen content that carries no dates at all (that case is FC-01, lower severity).
- FC-03 (medium) blog/news-style URLs exist but expose no machine-readable dates. Mechanism: visible dates help humans; structured dates are what machines actually compare.
- FC-04 (low) footer copyright year 2+ years behind. Mechanism: a small, universally understood abandonment signal.

## Identity: which entity do these facts belong to

- FC-05 (high) no Organization, LocalBusiness, or WebSite JSON-LD anywhere. Mechanism: without an authoritative self-declaration, machines assemble the entity from scattered prose, and same-named entities bleed into each other.
- FC-08 (medium) ambiguity risk: brand presents as a 1-2 word name with no meta description and no Organization markup. Mechanism: mistaken identity is a Round-2 failure mode; short generic names need explicit category framing to disambiguate.
- FC-09 (low) brand name absent from most page titles. Mechanism: cross-page name consistency is how machines bind content to the entity.

## Corroboration: does anything independent agree

- FC-06 (medium) no sameAs and no outbound links to any independent profile host (Wikipedia, Wikidata, LinkedIn, GitHub, Crunchbase, review platforms, social). Mechanism: machines trust facts stated consistently across unrelated sources; an island site is a single fragile assertion.
- FC-07 (medium) Organization markup exists but sameAs is empty. Mechanism: sameAs is the strongest explicit disambiguation and corroboration pointer; omitting it wastes the markup that already exists.
- FC-10 (medium) no discoverable About page. Mechanism: "who is X" is the canonical assistant query about a brand; the About page is the quotable self-description that answers it.

## Optional manual off-site corroboration (not automated on purpose)

The contest permits checking community platforms (Reddit, Quora, review sites) for brand visibility. This marketplace deliberately keeps that out of the automated path: those platforms rate-limit and block datacenter clients unpredictably, and the guidelines warn against depending on third-party services that can go down. When performing this manually, search each platform for the exact brand name plus its category, and record: whether the brand is mentioned at all, whether facts stated there match the site, and whether a different same-named entity dominates the results. Feed confirmed mismatches back as evidence under FC-06/FC-08.

## Answer and generative engine optimization (AEO / GEO)

These checks ask whether content is shaped so assistants can lift and attribute it, not just whether it exists.

- FC-11 (medium) no answer-shaped content. Fires when a sample of 3+ pages contains zero question-form H2/H3 headings (ends with ? or starts with a question word) and no FAQPage markup. Mechanism: assistants match user questions against question-shaped headings and quote the paragraph beneath; a site with none is structurally hard to cite.
- FC-12 (low) no /llms.txt. Fires when the crawl's llms.txt probe found nothing; the probe rejects soft-404s (HTTP 200 HTML answers and redirects away from /llms.txt), so a CMS's catch-all 200 page cannot suppress this finding. Mechanism: an emerging convention that hands AI crawlers a curated map of the most quotable pages, shaping what assistants read first.
- FC-13 (medium) no quotable one-sentence brand definition. Fires when the brand token is 3+ characters, the homepage has 300+ characters of text, and neither the homepage body nor the meta description contains a self-contained sentence of at most about 220 characters naming the brand with a linking verb (is, provides, offers, builds, makes, delivers, creates, specializes). Mechanism: generative engines compose answers from sentences they can lift cleanly; without one, they paraphrase, and paraphrases drift.
- FC-14 (medium) structured-data coverage gap. Fires only when some JSON-LD already exists (zero markup is CR-07's finding) yet article-style pages (blog/news/article/post URLs) lack Article/BlogPosting/NewsArticle types, or product/pricing-style pages (product/shop/pricing/plans URLs, or visible price patterns) lack Product/Offer/Service types. Mechanism: engines index articles and products correctly only when the matching schema type states what each page is.

## Corroboration depth

- FC-15 (low) corroboration rests on a single external profile. Fires when no sameAs exists and exactly one independent profile host is linked site-wide (zero of both is FC-06, medium). Mechanism: machines triangulate facts across independent sources; one source is a thin base.

## Sitemap freshness

- FC-16 (medium) sitemap advertises stale content. Fires when a sitemap exists, exposes lastmod dates, and the newest one is 2+ years old. Mechanism: the sitemap is the site's own machine-readable statement of what changed and when; one that says nothing has changed in years tells crawlers and AI retrieval systems to deprioritize revisits, independent of how fresh the visible content is. Read from the crawl snapshot; costs no extra request.
