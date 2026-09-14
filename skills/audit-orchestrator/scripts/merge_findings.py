"""merge_findings.py -- concrete, defined deduplication algorithm."""
import re

_STOPWORDS = {"a", "an", "the", "is", "are", "was", "were", "be", "been", "of", "to",
              "in", "on", "for", "with", "and", "or", "that", "this", "it", "its",
              "as", "by", "at", "from", "has", "have", "had"}


def normalize_text(text: str) -> str:
    text = (text or "").lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    tokens = [t for t in tokens if t not in _STOPWORDS]
    lemmas = []
    for t in tokens:
        for suf in ("ing", "edly", "ed", "es", "s"):
            if t.endswith(suf) and len(t) - len(suf) >= 3:
                t = t[: -len(suf)]
                break
        lemmas.append(t)
    return " ".join(sorted(lemmas))


def dedup_key(finding: dict) -> tuple:
    normalized_cause = normalize_text(finding["root_cause"])
    return (
        finding["category"],
        normalized_cause,
        tuple(sorted(finding.get("affected_pages") or [])) or ("site-wide",),
    )


def _token_set(s: str) -> set:
    return set(s.split())


def similarity(a: str, b: str) -> float:
    ta, tb = _token_set(a), _token_set(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _is_robots_inaccessible_finding(finding: dict) -> bool:
    cid = finding.get("check_id") or (finding.get("provenance") or {}).get("rule_id")
    if cid in ("robots-unreachable", "ai-crawler-unchecked"):
        return True
    if cid == "fetch-failure":
        urls = list(finding.get("affected_pages") or []) + [
            u for e in (finding.get("evidence") or []) if isinstance(e, dict) for u in e.get("urls", [])
        ]
        if any(isinstance(u, str) and (u.endswith("/robots.txt") or "/robots.txt" in u) for u in urls):
            return True
    return False


def find_matching_bucket(finding: dict, buckets: dict, similarity_threshold: float = 0.85):
    if _is_robots_inaccessible_finding(finding):
        cascade_key = ("ai_discoverability", "robots-inaccessible-cascade", ("site-wide",))
        return cascade_key if cascade_key in buckets else None
    key = dedup_key(finding)
    if key in buckets:
        return key
    cat = finding["category"]
    scope = tuple(sorted(finding.get("affected_pages") or [])) or ("site-wide",)
    norm_cause = normalize_text(finding["root_cause"])
    for existing_key in buckets:
        e_cat, e_cause, e_scope = existing_key
        if e_cat == cat and e_scope == scope and similarity(norm_cause, e_cause) >= similarity_threshold:
            return existing_key
    return None


def _evidence_key(item: dict) -> tuple:
    """Canonical, hashable key for one evidence entry, used to drop exact
    duplicates when merging evidence from multiple contributing findings."""
    return (
        item.get("type"),
        item.get("description"),
        tuple(sorted(item.get("urls") or [])),
    )


def merge_evidence(group: list) -> dict:
    best = max(group, key=lambda f: (f.get("confidence", 0), 1 if f.get("check_id") == "robots-unreachable" else 0))
    evidence, provenance = [], []
    seen_evidence = set()
    for f in group:
        for item in f.get("evidence") or []:
            key = _evidence_key(item)
            if key in seen_evidence:
                continue
            seen_evidence.add(key)
            evidence.append(item)
        provenance.append(f.get("provenance"))
    merged = dict(best)
    merged["check_ids"] = sorted({f["check_id"] for f in group if f.get("check_id")})
    merged["evidence"] = evidence
    from models import make_evidence_text
    merged["evidence_text"] = make_evidence_text(evidence)
    merged["provenance"] = {"contributing_skills": provenance}
    all_pages = sorted(set(p for f in group for p in (f.get("affected_pages") or [])))
    if all_pages:
        merged["affected_pages"] = all_pages
    return merged


def merge_findings(results: list) -> list:
    """Input MUST be list[SkillResult]; intermediate artifacts are rejected outright."""
    for r in results:
        if "skill" not in r or "findings" not in r:
            raise ValueError("merge_findings accepts SkillResult objects only")

    buckets: dict = {}
    all_findings = [f for r in results for f in r["findings"]]
    for finding in all_findings:
        if _is_robots_inaccessible_finding(finding):
            key = ("ai_discoverability", "robots-inaccessible-cascade", ("site-wide",))
        else:
            match = find_matching_bucket(finding, buckets, similarity_threshold=0.85)
            key = match or dedup_key(finding)
        buckets.setdefault(key, []).append(finding)
    return [merge_evidence(group) for group in buckets.values()]
