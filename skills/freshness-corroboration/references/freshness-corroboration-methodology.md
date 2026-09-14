# Freshness & corroboration methodology

Entity resolution hierarchy: Organization/Product JSON-LD -> legal/registered
name on first-party pages -> canonical domain -> address/phone -> sameAs and
official social profiles -> consistent first-party naming.

Confidence gates: >=0.85 (ambiguity empty) allows broad identity-aware
external analysis; 0.65-0.849 restricts to domain-led sources and marks
partial; <0.65 or unresolved ambiguity suppresses external search and returns
insufficient_evidence.

Footprint calibration: search non-detection is never proof of real-world
absence. Footprint findings are always category=off_site_presence,
finding_type=proactive_improvement -- never critical or high solely because
few sources were found.
