#!/usr/bin/env python3
"""
Entrypoint: Findings Merger & Prioritizer (merge_and_prioritize.py)
Dual-mode merger reading from file arguments (globbing) or standard input (pipe),
deduplicating by title, enforcing severity order, assigning sequential IDs (F-001...),
and emitting the final validated Brand AI-Readiness report JSON.
Pure Python 3 stdlib - zero external dependencies.
"""

import sys
import json
from datetime import datetime, timezone

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

def load_inputs(args):
    """Load findings and proactive items from file arguments or stdin with robust type discrimination."""
    all_findings = []
    all_proactive = []

    def ingest(data):
        if isinstance(data, list):
            for item in data:
                ingest(item)
        elif isinstance(data, dict):
            # 1. Container dict containing findings and/or proactive recommendations
            if "findings" in data or "proactive_recommendations" in data:
                findings_val = data.get("findings")
                if isinstance(findings_val, list):
                    all_findings.extend(findings_val)
                proactive_val = data.get("proactive_recommendations")
                if isinstance(proactive_val, list):
                    all_proactive.extend(proactive_val)
            # 2. Standalone proactive recommendation object (fixes ingest fallback bug)
            elif "impact" in data or ("suggested_action" in data and "severity" not in data and "category" not in data):
                all_proactive.append(data)
            # 3. Standalone finding object
            else:
                all_findings.append(data)

    # 1. If file arguments are passed (e.g. merge.py <URL> /tmp/audit_runs/*.json)
    if len(args) > 2:
        for fpath in args[2:]:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        ingest(json.loads(content))
            except Exception as err:
                sys.stderr.write(f"[WARN] Error reading {fpath}: {err}\n")

    # 2. Or if input is piped through stdin
    elif not sys.stdin.isatty():
        content = sys.stdin.read().strip()
        if content:
            try:
                ingest(json.loads(content))
            except json.JSONDecodeError:
                decoder = json.JSONDecoder()
                content = content.lstrip()
                while content:
                    try:
                        obj, idx = decoder.raw_decode(content)
                        ingest(obj)
                        content = content[idx:].lstrip()
                    except json.JSONDecodeError:
                        content = content[1:].lstrip()

    return all_findings, all_proactive

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: merge_and_prioritize.py <URL> [file1.json file2.json ...]\n")
        sys.exit(1)

    target_url = sys.argv[1]
    raw_findings, raw_proactive = load_inputs(sys.argv)

    # Deduplicate findings by title and normalize severity
    seen_titles = set()
    deduped_findings = []
    for f in raw_findings:
        if not isinstance(f, dict):
            continue
        title = str(f.get("title") or "").strip()
        norm_title = title.lower()
        if norm_title and norm_title not in seen_titles:
            seen_titles.add(norm_title)
            # Normalize severity to lowercase to prevent sorting/counting drift
            sev = str(f.get("severity", "low")).lower().strip()
            f["severity"] = sev if sev in SEVERITY_ORDER else "low"
            f["title"] = title
            deduped_findings.append(f)

    # Invariant I-1: Evidence-sufficiency gating (prevent overclaiming from inconclusive evidence)
    INSUFFICIENCY_MARKERS = (
        "unverifiable", "insufficient", "unable to confirm",
        "search plugin unavailable", "search tool unavailable",
        "corroboration unavailable", "evidence inconclusive",
        "could not be verified", "0 corroborating"
    )
    for f in deduped_findings:
        scan_text = (
            str(f.get("title") or "") + " " +
            str(f.get("evidence") or "") + " " +
            str(f.get("mechanism") or "")
        ).lower()
        if any(marker in scan_text for marker in INSUFFICIENCY_MARKERS):
            if f.get("severity") in ("critical", "high", "medium"):
                f["severity"] = "low"
                f["evidence"] = str(f.get("evidence", "")) + " [Note: Severity capped to low due to inconclusive/insufficient evidence per Invariant I-1]."

    # Sort strictly by priority matrix severity
    deduped_findings.sort(key=lambda x: SEVERITY_ORDER.get(str(x.get("severity", "low")).lower().strip(), 4))

    # Assign deterministic sequential IDs: F-001, F-002...
    summary_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for idx, f in enumerate(deduped_findings, start=1):
        f["id"] = f"F-{idx:03d}"
        sev = f.get("severity", "low")
        if sev in summary_counts:
            summary_counts[sev] += 1

    # Deduplicate proactive recommendations
    seen_proactive = set()
    deduped_proactive = []
    for p in raw_proactive:
        if not isinstance(p, dict):
            continue
        title = str(p.get("title") or "").strip()
        norm_title = title.lower()
        if norm_title and norm_title not in seen_proactive:
            seen_proactive.add(norm_title)
            p["title"] = title
            deduped_proactive.append(p)

    final_report = {
        "site": target_url,
        "audited_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": {
            "total_findings": len(deduped_findings),
            "critical": summary_counts["critical"],
            "high": summary_counts["high"],
            "medium": summary_counts["medium"],
            "low": summary_counts["low"],
        },
        "findings": deduped_findings,
        "proactive_recommendations": deduped_proactive,
    }

    print(json.dumps(final_report, indent=2))

if __name__ == "__main__":
    main()
