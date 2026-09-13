"""fixtures_server.py -- a tiny local HTTP server used by integration tests so they
never depend on outbound network access. Exercises: normal pages, robots.txt
variants, redirects, malformed JSON-LD, slow/timeout-inducing endpoints, JS-heavy
(CSR) pages, orphan pages, a multi-brand identity conflict, a stale-commercial-facts
product page, and a broken-navigation (sitemap-only, isolated) page cluster."""
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_ROBOTS_ALLOW_ALL = "User-agent: *\nDisallow:\n"
_ROBOTS_DISALLOW_ALL = "User-agent: *\nDisallow: /\n"

_HOME = """<html><head><title>Example Brand</title>
<script type="application/ld+json">{"@type": "Organization", "name": "Example Brand",
"telephone": "+1 555-123-4567", "sameAs": ["https://twitter.com/example"]}</script>
</head><body><h1>Welcome</h1><p>Example Brand was founded 2015-01-01.</p>
<a href="/about">About</a><a href="/js-heavy">App</a><a href="/malformed">Malformed</a>
<a href="/redirect">Redirect</a><a href="/product">Product</a></body></html>"""

# Second, unrelated Organization JSON-LD block appended to the home page when
# multi_brand=True -- a genuine multi-brand-conflict case (v4.0 section 4 /
# resolve_entity_identity.py), distinct from harmless legal-suffix/case noise.
_MULTI_BRAND_EXTRA_JSONLD = (
    '<script type="application/ld+json">{"@type": "Organization", '
    '"name": "Zenith Traders", "telephone": "+1 555-000-1111"}</script>'
)

# Stale commercial fact: page_type resolves to "product" via the /product path,
# so its date claims are categorized "commercial" (assess_freshness.py) -- old
# dates here should surface as a high-severity finding. Three distinct dated
# mentions (not one) so the finding's evidence sample clears the full-confidence
# threshold in step_down_severity rather than being stepped down for a thin
# sample (models.step_down_severity, threshold=0.5 of a 3-fact reference sample).
_PRODUCT = """<html><head><title>Product</title></head><body><h1>Widget</h1>
<p>Price: $49.99. Offer last updated 2019-03-01.</p>
<p>Promotion valid through 2020-06-15.</p>
<p>Stock refreshed 2021-11-20.</p></body></html>"""

# Broken-navigation pair: mutually linked to each other, but linked from nowhere
# else on the site (discovered only via sitemap.xml, never via HOME's links) --
# a weakly-connected component isolated from the main site graph
# (build_site_graph.py isolated_clusters), not just two individual orphans.
_CLUSTER_A = ('<html><head><title>Cluster A</title></head><body><h1>Cluster A</h1>'
              '<a href="/cluster-b">Next</a></body></html>')
_CLUSTER_B = ('<html><head><title>Cluster B</title></head><body><h1>Cluster B</h1>'
              '<a href="/cluster-a">Back</a></body></html>')

_ABOUT = """<html><head><title>About</title></head><body><h1>About</h1>
<p>Contact us at +1 555-987-6543.</p></body></html>"""

_MALFORMED = """<html><head><title>Bad JSON-LD</title>
<script type="application/ld+json">{not valid json,,,}</script>
</head><body><h1>Page</h1><p>Some content here.</p></body></html>"""

_JS_HEAVY = (
    '<html><head><title>App</title></head><body><div id="root"></div>'
    "<script>document.getElementById('root').innerText = "
    "'Rendered content only visible after JavaScript execution. '.repeat(20);</script>"
    "</body></html>"
)

_ORPHAN = "<html><head><title>Orphan</title></head><body><h1>Orphan</h1>" \
          "<p>Nobody links here.</p></body></html>"


_SITEMAP_OK = ("<?xml version='1.0' encoding='UTF-8'?>"
               "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
               "<url><loc>{origin}/</loc></url><url><loc>{origin}/about</loc></url>"
               "</urlset>")
_SITEMAP_MALFORMED = "<urlset><url><loc>not closed"
# Lists /cluster-a and /cluster-b so they are discovered and crawled even though
# no page other than each other links to them -- the sitemap-discovery path
# (v4.0 section 0 / acquire_site.py) is what makes them reachable at all, and
# their mutual-only linking is what makes them an isolated cluster once crawled.
_SITEMAP_BROKEN_NAV = ("<?xml version='1.0' encoding='UTF-8'?>"
                       "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
                       "<url><loc>{origin}/</loc></url><url><loc>{origin}/about</loc></url>"
                       "<url><loc>{origin}/cluster-a</loc></url>"
                       "<url><loc>{origin}/cluster-b</loc></url>"
                       "</urlset>")


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "FixtureHTTP/1.0"
    robots_body = _ROBOTS_ALLOW_ALL
    robots_mode = "ok"  # "ok" | "absent" | "malformed" | "timeout" | "error"
    slow_delay_s = 0.0
    sitemap_mode = "absent"  # "absent" | "ok" | "malformed" | "broken_nav"
    llms_txt_mode = "absent"  # "absent" | "ok"
    big_body_bytes = 0  # if >0, /big serves this many bytes
    multi_brand = False  # if True, home page carries a second, unrelated Organization block

    def log_message(self, fmt, *args):  # silence test output
        pass

    def _send(self, status, body, headers=None):
        self.send_response(status)
        for k, v in (headers or {"Content-Type": "text/html"}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            if isinstance(body, str):
                body = body.encode("utf-8")
            self.wfile.write(body)

    def do_GET(self):
        path = self.path
        origin = f"http://{self.headers.get('Host', '127.0.0.1')}"
        if path == "/robots.txt":
            if self.robots_mode == "absent":
                self._send(404, "not found")
            elif self.robots_mode == "malformed":
                self._send(200, b"\xff\xfe\x00not valid utf-8 \x80\x81", {"Content-Type": "text/plain"})
            elif self.robots_mode == "timeout":
                time.sleep(self.slow_delay_s or 2.0)
                self._send(200, self.robots_body, {"Content-Type": "text/plain"})
            elif self.robots_mode == "error":
                self._send(500, "error", {"Content-Type": "text/plain"})
            else:
                self._send(200, self.robots_body, {"Content-Type": "text/plain"})
        elif path == "/sitemap.xml":
            if self.sitemap_mode == "ok":
                self._send(200, _SITEMAP_OK.format(origin=origin), {"Content-Type": "application/xml"})
            elif self.sitemap_mode == "broken_nav":
                self._send(200, _SITEMAP_BROKEN_NAV.format(origin=origin), {"Content-Type": "application/xml"})
            elif self.sitemap_mode == "malformed":
                self._send(200, _SITEMAP_MALFORMED, {"Content-Type": "application/xml"})
            else:
                self._send(404, "not found")
        elif path == "/llms.txt":
            if self.llms_txt_mode == "ok":
                self._send(200, "# Example Brand\n", {"Content-Type": "text/plain"})
            else:
                self._send(404, "not found")
        elif path == "/":
            home = _HOME
            if self.multi_brand:
                home = home.replace("</head>", _MULTI_BRAND_EXTRA_JSONLD + "</head>")
            self._send(200, home)
        elif path == "/about":
            self._send(200, _ABOUT)
        elif path == "/malformed":
            self._send(200, _MALFORMED)
        elif path == "/js-heavy":
            self._send(200, _JS_HEAVY)
        elif path == "/orphan":
            self._send(200, _ORPHAN)
        elif path == "/product":
            self._send(200, _PRODUCT)
        elif path == "/cluster-a":
            self._send(200, _CLUSTER_A)
        elif path == "/cluster-b":
            self._send(200, _CLUSTER_B)
        elif path == "/redirect":
            self._send(301, "", {"Location": "/about", "Content-Type": "text/html"})
        elif path == "/redirect-external":
            self._send(302, "", {"Location": "http://example.invalid.test/elsewhere",
                                  "Content-Type": "text/html"})
        elif path == "/big":
            self._send(200, b"x" * self.big_body_bytes, {"Content-Type": "application/octet-stream"})
        elif path == "/slow":
            time.sleep(self.slow_delay_s)
            self._send(200, "<html><body>slow</body></html>")
        elif path == "/error":
            self._send(500, "<html><body>error</body></html>")
        else:
            self._send(404, "<html><body>not found</body></html>")


def start_server(robots_body: str = _ROBOTS_ALLOW_ALL, slow_delay_s: float = 0.0,
                  robots_mode: str = "ok", sitemap_mode: str = "absent",
                  llms_txt_mode: str = "absent", big_body_bytes: int = 0,
                  multi_brand: bool = False):
    """Starts a background server on 127.0.0.1 with an OS-assigned port. Returns
    (base_url, shutdown_fn)."""
    handler = type("BoundFixtureHandler", (FixtureHandler,), {
        "robots_body": robots_body, "slow_delay_s": slow_delay_s, "robots_mode": robots_mode,
        "sitemap_mode": sitemap_mode, "llms_txt_mode": llms_txt_mode, "big_body_bytes": big_body_bytes,
        "multi_brand": multi_brand,
    })
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]

    def shutdown():
        httpd.shutdown()
        httpd.server_close()

    return f"http://127.0.0.1:{port}", shutdown
