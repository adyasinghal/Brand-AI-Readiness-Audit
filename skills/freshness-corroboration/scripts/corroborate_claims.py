"""corroborate_claims.py -- consumes the shared identity artifact; bounded external
checks (v4.0 section 8.3). No outbound web access in this sandboxed reference
implementation, so results are reported as insufficient evidence, never as a
confirmed contradiction."""
from models import insufficient_evidence_result


def corroborate_claims(facts, entity_identity, artifacts, deadline, limits):
    if entity_identity.get("status") not in ("success", "partial"):
        return insufficient_evidence_result(
            "freshness-corroboration", "Entity identity unresolved; corroboration suppressed."
        )
    return insufficient_evidence_result(
        "freshness-corroboration",
        "External corroboration requires outbound web access not available in this "
        "environment; claims are reported as insufficient evidence, not confirmed or contradicted.",
        metrics={"claims_checked": 0, "claims_corroborated": 0},
    )
