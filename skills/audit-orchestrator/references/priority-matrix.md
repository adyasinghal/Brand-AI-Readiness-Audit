# Brand AI-Readiness Audit — Priority Matrix & Decision Rules

This reference defines the deterministic priority rules enforced by `merge_and_prioritize.py` and all sub-skills.

## Universal Severity Tiers

| Severity | Retrieval Funnel Impact | Deterministic Trigger Rule | Concrete Examples |
|---|---|---|---|
| **critical** | **Total Invisibility:** Content cannot be reached, fetched, or indexed by AI crawlers. | Blocks machine crawling at the network or protocol level; or serves an empty page. | `robots.txt` disallowing AI bots; `noindex`/`nosnippet` meta tags; 100% empty CSR shell (zero server-rendered text). |
| **high** | **Factual Fragmentation:** Content is found, but key entity facts cannot be parsed or are locked in opaque media. | Missing machine-readable structured entities; or critical specifications trapped in client JS / images without text. | Missing baseline JSON-LD (`Organization`/`WebSite`); missing `sameAs` links; partial CSR render gap; prices only in images. |
| **medium** | **Degraded Authority / Bounce Friction:** Content is parsed, but trust signals are weak or on-site experience drives visitors away. | Stale recency indicators, incomplete social graph data, mobile friction, or intrusive blockers. | Stale copyright (>2 years old); missing OpenGraph/Twitter card tags; intrusive interstitials; missing viewport; brand name mismatch; stale or missing sitemap.xml. |
| **low** | **Proactive Optimization:** Standard compliance achieved, but forward-looking AI opportunities are missed. | Emerging AI machine standards, gated vertical schema opportunities, or newsletter summarization hygiene. | Missing `/llms.txt`; detected vertical signal without schema (e.g. e-commerce signals but no `Product` schema); Appendix F email digest optimization; missing `<lastmod>` in sitemap. |

## Structural Invariant I-1 (Evidence-Sufficiency Gating)

Any finding whose evidence or mechanism indicates that automated or external verification was inconclusive, unavailable, or partial (e.g., search plugin unavailable, corroboration unverifiable) **MUST** have its severity capped to `low`. Under no circumstances may an ungrounded or inconclusive signal be reported as a confirmed `critical`, `high`, or `medium` defect.
