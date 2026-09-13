---
name: freshness-corroboration
description: Extracts factual claims from a crawled website, ranks the most
  important ones, resolves a single disambiguated brand identity, and assesses
  whether those facts are fresh and corroborated by independent sources --
  calibrated so that insufficient external evidence is never reported as a
  confirmed defect. Called by audit-orchestrator; not intended to be invoked
  standalone.
license: MIT
allowed-tools: [network-fetch]
---

# Freshness & Corroboration

## When to use
Called by audit-orchestrator. `extract_claims`, `resolve_entity_identity`, and
`build_site_graph`-adjacent data steps run in the independent batch;
`identify_important_facts` runs once, sequentially, between the two batches;
`assess_freshness`, `corroborate_claims`, and `assess_external_footprint` run in
the dependent batch.

## Dependencies
`extract_claims`, `identify_important_facts`, `resolve_entity_identity`, and
`assess_freshness` are pure-Python, no network. `corroborate_claims` and
`assess_external_footprint` call the pluggable `common/search_provider.py`
(optional capability, `requests`-based) -- gated on `SEARCH_API_URL` being set;
unset or failing degrades to `insufficient_evidence`, never a confirmed
absence (v4.0 section 5).

## Inputs
`AuditArtifacts`, the `claims` intermediate artifact, and the shared
`entity_identity` artifact (resolved once, reused by every consumer).

## Procedure
See `references/freshness-corroboration-methodology.md` for the entity
resolution hierarchy and footprint calibration table.

## Output
`SkillResult`s per analysis script, plus the `claims`, `important_facts`, and
`entity_identity` intermediate artifacts consumed by other steps.

## Example

A `/product` page with a 2019 date and no offsetting recent update:

```json
{"skill": "freshness-corroboration", "status": "success",
 "findings": [{"id": "F-004", "category": "freshness", "severity": "high",
               "status": "suspected",
               "root_cause": "Dated content classified as 'commercial' appears outdated"}],
 "metrics": {"date_facts_found": 3, "stale_facts": 3}}
```
