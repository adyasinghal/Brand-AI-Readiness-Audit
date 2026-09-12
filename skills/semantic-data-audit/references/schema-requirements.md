# Schema.org Structured Data Requirements & Gating Standards

This reference documents the structural criteria enforced by `parse_structured_data.py` to ensure high-fidelity fact extraction for Generative Engine Optimization (GEO) and LLM search agents.

## 1. Universal Baseline Entities (Mandatory)

Every domain must declare at least one primary identity anchor at root:

### `Organization` / `Corporation` / `Brand`
```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Brand Official Name",
  "url": "https://example.com",
  "logo": "https://example.com/logo.png",
  "sameAs": [
    "https://twitter.com/brand",
    "https://www.linkedin.com/company/brand",
    "https://www.wikidata.org/wiki/Q..."
  ]
}
```

### `WebSite`
```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Brand Official Site",
  "url": "https://example.com",
  "potentialAction": {
    "@type": "SearchAction",
    "target": "https://example.com/search?q={search_term_string}",
    "query-input": "required name=search_term_string"
  }
}
```

---

## 2. Gated Vertical Schemas (Signal-Triggered Only)

To prevent false positives on informational, blog, or academic sites, vertical schemas are only audited when clear on-page signals exist:

| Vertical | Required On-Page Signal | Target Schema | Recommended Schema Fields |
|---|---|---|---|
| **E-Commerce** | Price pattern (`$XX.XX`, `£XX.XX`) **AND** purchase intent (`Add to Cart`, `Buy Now`) | `Product` | `name`, `image`, `description`, `sku`, `offers` (`price`, `priceCurrency`, `availability`) |
| **Local Services** | Telephone links (`href="tel:"`) or opening hours (`Mon-Fri 9-5`) | `LocalBusiness` | `name`, `address`, `telephone`, `geo`, `openingHoursSpecification` |
| **FAQ / Q&A** | `<details>`, `<summary>`, or "Frequently Asked Questions" text | `FAQPage` | `mainEntity` array of `Question` and `acceptedAnswer` |
| **Hierarchical Nav** | Breadcrumb classes or delimiter characters (`Home > Shop > Item`) | `BreadcrumbList` | `itemListElement` array of `ListItem` (`position`, `name`, `item`) |

---

## 3. Recursive `@graph` Handling

Many CMS platforms (WordPress / Yoast / RankMath) nest all structured data inside an `@graph` array:
```json
{
  "@context": "https://schema.org",
  "@graph": [
    { "@type": "Organization", "@id": "https://example.com/#org", "name": "Brand" },
    { "@type": "WebSite", "@id": "https://example.com/#website", "url": "https://example.com" }
  ]
}
```
`parse_structured_data.py` uses recursive unpacking (`unpack_graph()`) to extract all nested `@type` nodes, ensuring zero missed schemas regardless of nesting depth.
