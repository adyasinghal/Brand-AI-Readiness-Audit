"""resolve_entity_identity.py -- runs once; centralized, disambiguated identity
resolution (v4.0 section 4)."""
from models import intermediate_artifact


def resolve_entity_identity(artifacts, deadline):
    org_blocks = [
        block for page in artifacts.pages for block in page.jsonld_blocks
        if isinstance(block, dict) and block.get("@type") in ("Organization", "Product", "LocalBusiness")
    ]

    if not org_blocks:
        return intermediate_artifact(
            "entity_identity", status="insufficient_evidence",
            data={"confidence": 0.0, "ambiguity_set": [], "entity_type": "unknown"},
            warnings=["No Organization/Product JSON-LD found; identity unresolved."],
        )

    primary = org_blocks[0]
    name = primary.get("name") or artifacts.normalized_origin
    aliases = sorted({b.get("name") for b in org_blocks if b.get("name")})
    confidence = 0.9 if len(aliases) <= 1 else 0.7
    ambiguity_set = aliases[1:] if len(aliases) > 1 else []

    same_as = primary.get("sameAs", [])
    if isinstance(same_as, (list, tuple)):
        same_as = list(same_as)
    else:
        same_as = [same_as] if same_as else []

    data = {
        "canonical_name": name,
        "legal_name": primary.get("legalName", name),
        "domain": artifacts.normalized_origin,
        "normalized_address": primary.get("address"),
        "phone_numbers": [primary.get("telephone")] if primary.get("telephone") else [],
        "same_as_urls": same_as,
        "social_handles": [],
        "aliases": list(aliases) or [name],
        "entity_type": str(primary.get("@type", "organization")).lower(),
        "identity_fingerprint": f"{name.lower()}::{artifacts.normalized_origin}",
        "confidence": confidence,
        "ambiguity_set": ambiguity_set,
        "disambiguation_evidence": [],
    }
    status = "success" if confidence >= 0.85 else "partial"
    return intermediate_artifact("entity_identity", data=data, status=status)
