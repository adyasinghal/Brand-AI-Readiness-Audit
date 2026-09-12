---
name: engagement-friction-audit
description: Stage 4 Visitor Retention Audit. Evaluates mobile responsive viewport configuration, intrusive interstitial overlays/modals, above-the-fold content density, deep-link routing accessibility, and email newsletter capture formatting for inbox AI summarizers (Apple Intelligence Mail, Gmail Gemini, Appendix F). Use when diagnosing post-click referral bounce rates and visitor drop-off from AI assistant citations.
---

# Stage 4: Visitor Retention & Engagement Friction Audit

Audits on-site engagement factors that determine whether visitors referred by AI assistants bounce or stay.

## Execution Procedure
1. Execute the friction audit script against the target URL:
   ```bash
   python3 skills/engagement-friction-audit/scripts/check_friction.py <URL>
   ```
2. The script deterministically evaluates:
   - Mobile viewport tag configuration (`<meta name="viewport">` in `<head>`).
   - Intrusive interstitial or modal backdrop patterns that block immediate answer discovery.
   - Deep-link accessibility (clean path routing vs hash-only SPA fragments).
   - Semantic heading hierarchy (primary `<h1>` topic anchor presence and single-heading consolidation).
   - **Appendix F Fast Email Check:** Uses fast non-blocking string matching to detect email newsletter forms. If detected, emits proactive recommendations for clean plain-text MIME fallbacks and front-loaded CTAs to survive inbox AI summarizers.
   - Reuses `/tmp/audit_runs/page.html` cache file if available to prevent redundant HTTP requests.
