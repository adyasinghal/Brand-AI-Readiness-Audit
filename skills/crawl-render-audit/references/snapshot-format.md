# site_snapshot.json format

The contract between crawl-render-audit (producer) and the analysis skills (consumers). One crawl, many analyses: the site is fetched exactly once per audit, which is both polite and fast.

```json
{
  "base_url": "https://example.com",
  "host": "example.com",
  "fetched_at": "2026-09-20T14:32:00Z",
  "robots": {
    "status": 200,
    "ai_crawlers_blocked": ["GPTBot"],
    "sitemaps_declared": ["https://example.com/sitemap.xml"]
  },
  "sitemap_found": true,
  "sitemap_latest_lastmod_year": 2023,
  "llms_txt_present": false,
  "pages": [
    {
      "url": "https://example.com/",
      "status": 200,
      "final_url": "https://example.com/",
      "redirects": [ { "status": 301, "to": "https://example.com/" } ],
      "elapsed_ms": 412,
      "x_robots_tag": "",
      "error": null,
      "robots_blocked": false,
      "features": {
        "title": "Example Co - Industrial Sensors",
        "meta": { "description": "...", "viewport": "...", "og:site_name": "...", "robots": "..." },
        "canonical": "https://example.com/",
        "lang": "en",
        "headings": { "h1": ["..."], "h2": ["..."], "h3": ["..."] },
        "links": [ ["/about", "About us"] ],
        "images_total": 14,
        "images_missing_alt": 3,
        "script_count": 6,
        "script_bytes": 48211,
        "jsonld_types": ["Organization", "WebSite"],
        "jsonld_items": [ { "@type": "Organization", "name": "..." } ],
        "jsonld_parse_errors": 0,
        "jsonld_error_details": [],
        "has_nav": true,
        "has_noscript": false,
        "noscript_text": "",
        "has_search_input": false,
        "forms": 1,
        "buttons": ["Get a quote"],
        "paragraph_lengths": [140, 220, 90],
        "root_div_ids": [],
        "visible_text": "First 60000 chars of visible text ...",
        "text_len": 5341,
        "html_bytes": 88210,
        "word_count": 941,
        "top_term": "sensors",
        "top_term_ratio": 0.021,
        "title_sig_terms": 4,
        "title_terms_matched": 3,
        "question_headings": 2,
        "has_price_pattern": false,
        "heading_sequence": [1, 2, 3, 3, 2],
        "landmarks": ["footer", "header", "main"],
        "inputs_total": 2,
        "media_embeds": 0,
        "interactive_details": 0,
        "head_blocking_scripts": 1,
        "images_missing_dims": 3,
        "images_lazy": 8,
        "og_present": true,
        "twitter_present": false,
        "email_capture": false,
        "interstitial_signals": 0
      }
    }
  ]
}
```

Notes for consumers:
- `pages[0]` is always the homepage (or the failed attempt at it). Filter to `status == 200 and features` before analysis.
- `features` is null for non-200, non-HTML, or robots-blocked pages.
- `visible_text` is capped at 60000 characters; `links` at 800 entries; `jsonld_items` at 40. Design checks around ratios and presence, not exhaustive totals.
- `@graph` arrays in JSON-LD are flattened into `jsonld_items`. `jsonld_types` holds NORMALIZED type names: full URIs (https://schema.org/Organization), CURIE forms (schema:Organization), and array-valued @type all resolve to the bare name, so consumers match on plain strings like "Organization".
- `visible_text` excludes the `<title>` element (metadata, not rendered content) plus script, style, and noscript bodies.
- Derived keyword fields: `word_count` counts lowercase word tokens in the visible text; `top_term`/`top_term_ratio` describe the most frequent non-stopword of 4+ characters (only computed at 50+ words); `title_sig_terms` is the number of distinct non-stopword title terms of 4+ characters and `title_terms_matched` how many of them occur in the body text.
- `question_headings` counts H2/H3s that end in `?` or start with a question word (how, what, why, when, where, who, can, does, do, is, are, should, which).
- `heading_sequence` is the document-order list of heading levels (h1..h6), capped at 200 entries, for hierarchy analysis.
- `landmarks` lists which of main, article, header, footer appear; `has_nav` covers nav separately.
- `head_blocking_scripts` counts external scripts inside `<head>` with neither defer nor async and a non-module type.
- `inputs_total` covers input, select, and textarea; `media_embeds` covers video, audio, canvas, and iframe; `interactive_details` counts details elements.
- `images_missing_dims` counts img tags lacking width or height attributes; `images_lazy` counts loading="lazy" images.
- `x_robots_tag` is the raw X-Robots-Tag response header (empty when absent); noindex can arrive here as well as in the meta tag.
- `sitemap_latest_lastmod_year` is the newest year found in the sitemap's lastmod entries, or null.
- `jsonld_error_details` holds up to 3 parser messages with line and column for invalid blocks.
- `email_capture` is true when any input is email-typed or email-named; `interstitial_signals` counts elements with unambiguous popup class tokens.
- Fetches decompress forced-gzip responses (magic-byte detection) before decoding.
