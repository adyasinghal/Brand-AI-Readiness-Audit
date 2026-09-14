"""Shared, network-free helpers for snapshot check modules."""
from check_catalog import get_entry
from models import make_finding


def eligible_pages(artifacts):
    return [p for p in artifacts.pages if p.status_code == 200 and p.features
            and p.features.get('observation_version') == 2
            and not {'non_html_content', 'response_truncated_at_byte_budget', 'html_parse_incomplete'} & set(p.warnings)]


def observation(check_id, title, pages, details, *, skill='crawl-render-audit',
                script='analyze_metadata.py', severity='low', confirmed=False):
    """Absence-based heuristics default to suspected, low-priority opportunities."""
    entry = get_entry(check_id)
    return make_finding(
        category='ai_discoverability', finding_type='defect' if confirmed else 'proactive_improvement',
        severity=severity, status='confirmed' if confirmed else 'suspected',
        confidence=.95 if confirmed else .6, title=title,
        root_cause=entry['mechanism'],
        affected_pages=[p.url for p in pages],
        evidence=[{'type':'snapshot_observation', 'description':details[p.url], 'urls':[p.url]}
                  for p in pages[:10]],
        suggested_action={'summary':entry['implementation_detail'],
                          'steps':[entry['implementation_detail']], 'priority':severity,
                          'effort':'medium' if check_id in ('http-transport','heavy-html','fetch-latency') else 'low',
                          'expected_benefit':entry['expected_outcome'],
                          'verification':'Repeat the affected observation and verify the intended behavior.'},
        provenance={'skill':skill, 'script':script, 'rule_id':check_id})
