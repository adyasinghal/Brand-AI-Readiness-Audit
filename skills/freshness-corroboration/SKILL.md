---
name: freshness-corroboration
description: Extracts factual claims from a crawled website, ranks the most
  important ones, resolves a single disambiguated brand identity, and assesses
  whether those facts are fresh and corroborated by independent sources --
  calibrated so that insufficient external evidence is never reported as a
  confirmed defect. Called by audit-orchestrator; not intended to be invoked
  standalone.
license: MIT
---

# Freshness & Corroboration

## When to use
Called by audit-orchestrator. `extract_claims`, `resolve_entity_identity`, and
`build_site_graph`-adjacent data steps run in the independent batch;
`identify_important_facts` runs once, sequentially, between the two batches;
`assess_freshness`, `corroborate_claims`, and `assess_external_footprint` run in
the dependent batch.

## Inputs
`AuditArtifacts`, the `claims` intermediate artifact, and the shared
`entity_identity` artifact (resolved once, reused by every consumer).

## Procedure
See `references/freshness-corroboration-methodology.md` for the entity
resolution hierarchy and footprint calibration table.

## Output
`SkillResult`s per analysis script, plus the `claims`, `important_facts`, and
`entity_identity` intermediate artifacts consumed by other steps.
