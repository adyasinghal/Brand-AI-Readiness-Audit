"""build_site_graph.py -- immutable graph artifact: degree, orphan/dead-end status,
importance (v4.0 section 8.4)."""
from models import intermediate_artifact


def build_site_graph(artifacts, deadline):
    urls = {p.url for p in artifacts.pages}
    in_degree = {u: 0 for u in urls}
    out_degree = {u: 0 for u in urls}
    for p in artifacts.pages:
        out_degree[p.url] = len(p.internal_links)
        for link in p.internal_links:
            if link in in_degree:
                in_degree[link] += 1

    orphans = [u for u in urls if in_degree.get(u, 0) == 0 and u != artifacts.site_url]
    dead_ends = [u for u in urls if out_degree.get(u, 0) == 0]

    nodes = {
        u: {
            "in_degree": in_degree.get(u, 0),
            "out_degree": out_degree.get(u, 0),
            "is_orphan": u in orphans,
            "is_dead_end": u in dead_ends,
            "importance": min(1.0, in_degree.get(u, 0) / max(1, len(urls))),
        }
        for u in urls
    }

    return intermediate_artifact("site_graph", data={"nodes": nodes, "orphans": orphans, "dead_ends": dead_ends})
