# Execution policy

DAG: validate_input -> acquire_site (once) -> independent batch (8 jobs, thread
pool) -> identify_important_facts (sequential, CPU-only) -> dependent batch (4
jobs, same thread pool) -> merge_findings -> prioritize_findings ->
validate_report.

Budgets (seconds): ACQUISITION 110, RENDERING 55, EXTERNAL_ANALYSIS 55,
FINALIZATION_RESERVE 20, TOTAL_AUDIT_TIMEOUT 270. Worst case ~245s, 25s margin.

One shared, monotonic `AuditDeadline` governs every stage. A stage that
exhausts its budget returns partial or insufficient-evidence output; nothing
is silently dropped and a timeout is never treated as proof of a defect.
