#!/usr/bin/env python3
"""
run_audit.py - Marketplace entrypoint. One command, one report.

Resolves the sibling skills from marketplace.json, runs them in order
(crawl first, since it produces the shared snapshot; then freshness and
engagement over that snapshot), merges every skill's findings, adds
proactive beyond-defect suggestions, and emits the final audit report.

Usage:
  python3 skills/audit-orchestrator/scripts/run_audit.py https://example.com --out report.json
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
from datetime import datetime, timezone

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
SUBPROCESS_TIMEOUTS = {"crawl-render-audit": 200, "freshness-corroboration": 45,
                       "engagement-audit": 45, "external-footprint-audit": 60}

SKILL_SCRIPTS = {
    "crawl-render-audit": "scripts/crawl_audit.py",
    "freshness-corroboration": "scripts/freshness_audit.py",
    "engagement-audit": "scripts/engagement_audit.py",
    "external-footprint-audit": "scripts/footprint_audit.py",
}
FINDINGS_FILES = {
    "crawl-render-audit": "crawl_findings.json",
    "freshness-corroboration": "freshness_findings.json",
    "engagement-audit": "engagement_findings.json",
    "external-footprint-audit": "footprint_findings.json",
}


def marketplace_root():
    """This file lives at <root>/skills/audit-orchestrator/scripts/run_audit.py."""
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def load_manifest(root):
    with open(os.path.join(root, "marketplace.json"), encoding="utf-8") as fh:
        return json.load(fh)


def run_skill(root, skill_path, skill_id, cli_args):
    """Run one sub-skill script; never let one failure kill the audit."""
    script_rel = SKILL_SCRIPTS.get(skill_id)
    if not script_rel:
        return {"skill": skill_id, "ok": False, "note": "no runner registered for this skill id"}
    script = os.path.join(root, skill_path, script_rel)
    if not os.path.exists(script):
        return {"skill": skill_id, "ok": False, "note": "script not found: {}".format(script)}
    cmd = [sys.executable, script] + cli_args
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=SUBPROCESS_TIMEOUTS.get(skill_id, 60))
        ok = proc.returncode == 0
        note = (proc.stdout or "").strip() or (proc.stderr or "").strip()
        return {"skill": skill_id, "ok": ok, "note": note[:400]}
    except subprocess.TimeoutExpired:
        return {"skill": skill_id, "ok": False, "note": "timed out"}
    except Exception as e:
        return {"skill": skill_id, "ok": False, "note": "{}: {}".format(type(e).__name__, e)}


def collect_findings(workdir):
    merged = []
    for skill_id, fname in FINDINGS_FILES.items():
        path = os.path.join(workdir, fname)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            for f in data.get("findings", []):
                if isinstance(f, dict) and {"title", "severity", "evidence", "suggested_action"} <= set(f):
                    merged.append(f)
        except (json.JSONDecodeError, OSError):
            continue
    return merged


def proactive_suggestions(workdir, findings):
    """Beyond-defect recommendations, keyed to what the snapshot shows is absent."""
    snap = {}
    snap_path = os.path.join(workdir, "site_snapshot.json")
    if os.path.exists(snap_path):
        try:
            with open(snap_path, encoding="utf-8") as fh:
                snap = json.load(fh)
        except (json.JSONDecodeError, OSError):
            snap = {}
    checks_fired = {f.get("check") for f in findings}
    pages = [p for p in snap.get("pages", []) if p.get("status") == 200 and p.get("features")]
    all_types = set()
    for p in pages:
        all_types.update(p["features"].get("jsonld_types", []))

    out = []
    if pages and "FAQPage" not in all_types and "EN-09" not in checks_fired:
        out.append({
            "title": "Mark up existing FAQ content with FAQPage JSON-LD",
            "priority": "medium",
            "rationale": "FAQ-style content exists but is not marked up. Question-and-answer pairs in FAQPage markup are the single easiest format for assistants to lift into direct answers with attribution.",
        })
    if pages:
        out.append({
            "title": "Add a quotable one-paragraph brand definition to the homepage and About page",
            "priority": "medium",
            "rationale": "Assistants compose answers from sentences they can lift cleanly. A self-contained paragraph stating who the brand is, what it does, and for whom, repeated consistently on-site and in the Organization description, becomes the sentence machines quote.",
        })
        out.append({
            "title": "Seed and maintain presence on independent community and review platforms",
            "priority": "low",
            "rationale": "Assistants weight facts corroborated across unrelated sources. Accurate, consistent listings and organic mentions on community platforms (per contest scope: Reddit, Quora, review sites) reinforce the same facts the site states, making them safer for an assistant to repeat.",
        })
    return out[:4]


def main():
    ap = argparse.ArgumentParser(description="Brand AI-readiness audit (marketplace entrypoint)")
    ap.add_argument("url", help="Site to audit, e.g. https://example.com")
    ap.add_argument("--out", default="report.json")
    ap.add_argument("--workdir", default=None, help="Working directory (default: temp dir)")
    ap.add_argument("--max-pages", type=int, default=8)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--keep-workdir", action="store_true")
    ap.add_argument("--external-checks", action="store_true",
                    help="Also run the opt-in external-footprint-audit skill "
                         "(at most 3 keyless read-only queries to public endpoints, "
                         "never to the audited site)")
    args = ap.parse_args()

    root = marketplace_root()
    manifest = load_manifest(root)
    skills = {s["id"]: s["path"] for s in manifest.get("skills", [])}

    workdir = args.workdir or tempfile.mkdtemp(prefix="brand_audit_")
    os.makedirs(workdir, exist_ok=True)

    runs = []
    runs.append(run_skill(root, skills.get("crawl-render-audit", ""), "crawl-render-audit",
                          [args.url, "--workdir", workdir,
                           "--max-pages", str(args.max_pages), "--delay", str(args.delay)]))
    for skill_id in ("freshness-corroboration", "engagement-audit"):
        runs.append(run_skill(root, skills.get(skill_id, ""), skill_id, ["--workdir", workdir]))
    if args.external_checks:
        runs.append(run_skill(root, skills.get("external-footprint-audit", ""),
                              "external-footprint-audit", ["--workdir", workdir]))
    else:
        runs.append({"skill": "external-footprint-audit", "ok": True,
                     "note": "skipped by default; opt in with --external-checks"})

    findings = collect_findings(workdir)
    findings.sort(key=lambda f: (SEVERITY_RANK.get(f.get("severity"), 9), f.get("check", ""), f.get("title", "")))
    for i, f in enumerate(findings, 1):
        f["id"] = "F-{:03d}".format(i)
        # required key order first, extras after
        f_ordered = {"id": f["id"], "title": f["title"], "severity": f["severity"],
                     "evidence": f["evidence"], "suggested_action": f["suggested_action"],
                     "check": f.get("check"), "effort": f.get("effort"),
                     "source_skill": f.get("source_skill")}
        findings[i - 1] = f_ordered

    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    host = urllib.parse.urlsplit(args.url if "://" in args.url else "https://" + args.url).netloc
    report = {
        "site": host or args.url,
        "audited_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "summary": {
            "total_findings": len(findings),
            "critical": counts["critical"],
            "high": counts["high"],
            "medium": counts["medium"],
            "low": counts["low"],
        },
        "findings": findings,
        "proactive_suggestions": proactive_suggestions(workdir, findings),
        "audit_meta": {
            "marketplace": manifest.get("name"),
            "version": manifest.get("version"),
            "skill_runs": runs,
            "pages_sampled": _pages_sampled(workdir),
        },
    }

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print("\nBrand AI-Readiness Audit: {}".format(report["site"]))
    print("=" * 60)
    print("Findings: {}  (critical {}, high {}, medium {}, low {})".format(
        len(findings), counts["critical"], counts["high"], counts["medium"], counts["low"]))
    for f in findings:
        print("  [{}] {:8s} {}".format(f["id"], f["severity"].upper(), f["title"]))
    if report["proactive_suggestions"]:
        print("Proactive suggestions:")
        for s in report["proactive_suggestions"]:
            print("  [{}] {}".format(s["priority"].upper(), s["title"]))
    for r in runs:
        status = "ok" if r["ok"] else "DEGRADED"
        print("  skill {}: {} ({})".format(r["skill"], status, r["note"][:80]))
    print("Report written to {}".format(os.path.abspath(args.out)))

    if not args.keep_workdir and args.workdir is None:
        import shutil
        shutil.rmtree(workdir, ignore_errors=True)
    return 0


def _pages_sampled(workdir):
    try:
        with open(os.path.join(workdir, "site_snapshot.json"), encoding="utf-8") as fh:
            snap = json.load(fh)
        return [{"url": p["url"], "status": p["status"]} for p in snap.get("pages", [])]
    except (OSError, json.JSONDecodeError):
        return []


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)  # stdout consumer closed early; the report file is already written
