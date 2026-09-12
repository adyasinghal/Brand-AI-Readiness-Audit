# External footprint checks (EX-01, EX-02)

Opt-in checks. At most 3 keyless read-only GET requests, none to the audited
site. Every probe failure is recorded as a note and produces no finding.

- EX-01 (medium) domain absent from the Common Crawl corpus. Procedure: GET
  `https://index.commoncrawl.org/collinfo.json`, take the first (newest)
  collection's `cdx-api` value, then GET
  `<cdx-api>?url=<domain>&matchType=domain&limit=1&output=json`. Fires when
  the CDX query succeeds and returns an empty body. Mechanism: Common Crawl
  is the open corpus many AI training and retrieval pipelines derive from;
  zero captures there means the domain is invisible to that downstream
  ecosystem regardless of on-site quality. Skipped for localhost, bare-IP,
  and non-public hosts.

- EX-02 (low) no Wikipedia entity matches the brand name. Procedure: GET
  `https://en.wikipedia.org/w/api.php?action=opensearch&limit=5&format=json&search=<brand>`
  where brand is the og:site_name or the first segment of the homepage
  title. Fires when the API answers and no returned title equals or contains
  the brand token. Severity is low and the finding is phrased as an
  opportunity because absence is normal for smaller organizations; the
  suggested action points to the substitutes machines fall back on
  (Organization JSON-LD with sameAs, consistent platform profiles).

Positive results (domain present, entity found) are recorded in the skill's
`notes` output so the report reader sees the confirmation, not silence.

## Manual execution with curl

```
curl -s https://index.commoncrawl.org/collinfo.json | head
curl -s "<cdx-api>?url=example.com&matchType=domain&limit=1&output=json"
curl -s "https://en.wikipedia.org/w/api.php?action=opensearch&limit=5&format=json&search=ExampleBrand"
```
