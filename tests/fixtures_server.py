"""fixtures_server.py -- a tiny local HTTP server used by integration tests so they
never depend on outbound network access. Exercises: normal pages, robots.txt
variants, redirects, malformed JSON-LD, slow/timeout-inducing endpoints, JS-heavy
(CSR) pages, and orphan pages."""
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
<a href="/redirect">Redirect</a></body></html>"""

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


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "FixtureHTTP/1.0"
    robots_body = _ROBOTS_ALLOW_ALL
    slow_delay_s = 0.0

    def log_message(self, fmt, *args):  # silence test output
        pass

    def _send(self, status, body, headers=None):
        self.send_response(status)
        for k, v in (headers or {"Content-Type": "text/html"}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body.encode("utf-8"))

    def do_GET(self):
        path = self.path
        if path == "/robots.txt":
            self._send(200, self.robots_body, {"Content-Type": "text/plain"})
        elif path == "/":
            self._send(200, _HOME)
        elif path == "/about":
            self._send(200, _ABOUT)
        elif path == "/malformed":
            self._send(200, _MALFORMED)
        elif path == "/js-heavy":
            self._send(200, _JS_HEAVY)
        elif path == "/orphan":
            self._send(200, _ORPHAN)
        elif path == "/redirect":
            self._send(301, "", {"Location": "/about", "Content-Type": "text/html"})
        elif path == "/slow":
            time.sleep(self.slow_delay_s)
            self._send(200, "<html><body>slow</body></html>")
        elif path == "/error":
            self._send(500, "<html><body>error</body></html>")
        else:
            self._send(404, "<html><body>not found</body></html>")


def start_server(robots_body: str = _ROBOTS_ALLOW_ALL, slow_delay_s: float = 0.0):
    """Starts a background server on 127.0.0.1 with an OS-assigned port. Returns
    (base_url, shutdown_fn)."""
    handler = type("BoundFixtureHandler", (FixtureHandler,), {
        "robots_body": robots_body, "slow_delay_s": slow_delay_s,
    })
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]

    def shutdown():
        httpd.shutdown()
        httpd.server_close()

    return f"http://127.0.0.1:{port}", shutdown
