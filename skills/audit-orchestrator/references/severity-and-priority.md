# Severity and priority semantics

Prioritization is a scored contest differentiator, so both scales are defined by mechanism, not vibes.

## Severity (how badly this hurts today)

- critical: the content effectively does not exist for machines. The pipeline is severed at step one (cannot reach) or by explicit instruction (noindex, blanket robots disallow). Nothing downstream matters until this is fixed.
- high: the content is reachable but a whole class of consumers loses it or distrusts it: AI crawlers blocked by name, render gaps that empty the raw HTML, zero structured data, stale-looking facts, no way to contact, broken mobile rendering.
- medium: extraction or engagement is degraded, not severed: missing descriptions, no sitemap, walls of text, no FAQ, weak internal linking, uncorroborated identity.
- low: polish signals with real but small effect: copyright year, breadcrumbs, multiple H1s, missing search on small sites.

## Priority (what to fix first)

Each finding's `suggested_action.priority` defaults to its severity: impact ranks the queue, which matches the contest guidance that the most impactful problem gets the highest priority. The additive `effort` field (low/medium/high) lets a reader triage quick wins within a priority band: two high-priority items where one is a robots.txt line and the other is adopting server-side rendering are not the same afternoon.

Recommended reading order for a non-expert: fix criticals, then all `effort: low` highs and mediums (the quick wins), then the remaining highs, then everything else.

## False-positive discipline

Checks are written to fire only on countable evidence from the sampled pages (ratios, counts, explicit directives), never on absence of a single optional nicety. Every evidence string states the observed numbers so a skeptical reader can verify the claim against the site directly. Corpus-level checks (e.g. missing descriptions, alt text) require the pattern to hold across the sample majority before firing.
