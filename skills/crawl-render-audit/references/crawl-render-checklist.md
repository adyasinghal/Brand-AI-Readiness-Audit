# Crawl & render checklist

- robots.txt: general and AI-crawler-specific directives. Fetch status is one
  of `ok` / `absent` (404, allow-all) / `timeout` / `inaccessible` / `malformed`
  / `blocked` (failed the SSRF check). Only `ok` and `absent` produce a
  confirmed allow/disallow verdict; every other status is `insufficient_evidence`,
  never inferred as either an allow or a disallow.
- sitemap.xml: actually fetched and parsed (present/absent/inaccessible/malformed
  are distinguished; URLs are capped and available in `sitemap_data`).
- llms.txt: actually fetched (present/absent/inaccessible/blocked are
  distinguished; absence is `proactive_improvement` only, never a defect).
- HTTP status / broken pages
- Raw-vs-rendered content gaps (rendering-dependent checks report
  insufficient_evidence when no rendering was performed, never a defect)
- JSON-LD presence and coverage
- Semantic headings
