# Audit state schema

`AuditArtifacts` (frozen, read-only): `site_url`, `normalized_origin`, `pages`
(tuple of `PageArtifact`), `robots_data`, `llms_txt_data`, `sitemap_data`,
`acquisition_metadata`, `warnings`.

`PageArtifact` (frozen): acquisition-owned fields only -- url, status_code,
content_type, evidence_snippet, visible_text, title, meta_description,
canonical_url, headings, internal_links, external_links, jsonld_blocks,
page_type, fetch_duration_ms, render_status, breadcrumb_visible,
breadcrumb_schema, ai_crawler_directives, warnings.

No specialist may mutate, append to, or replace fields on either dataclass.
