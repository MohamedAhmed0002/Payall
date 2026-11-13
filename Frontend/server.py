from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
import json
import re
from pathlib import Path

BACKEND_URL = "http://127.0.0.1:8000"
PORT = 3000

API_ROUTES = {
    "GET": (
        re.compile(r"^/subscriptions$"),
        re.compile(r"^/categories$"),
        re.compile(r"^/catalog$"),
        re.compile(r"^/notifications$"),
        re.compile(r"^/history$"),
        re.compile(r"^/settings$"),
    ),
    "POST": (
        re.compile(r"^/subscriptions$"),
        re.compile(r"^/subscriptions/\d+/(payments|cancel)$"),
        re.compile(r"^/notifications/\d+/dismiss$"),
    ),
    "PATCH": (
        re.compile(r"^/subscriptions/\d+$"),
        re.compile(r"^/settings$"),
    ),
    "DELETE": (
        re.compile(r"^/subscriptions/\d+$"),
    ),
}


class ProxyHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            directory=str(Path(__file__).resolve().parent),
            **kwargs,
        )

    def api_route(self):
        parsed = urlsplit(self.path)
        routes = API_ROUTES.get(self.command, ())
        if parsed.path.startswith("/api/"):
            backend_path = parsed.path[4:]
            if any(route.fullmatch(backend_path) for route in routes):
                return parsed
        return None

    def reject_request(self, status=404):
        self.send_error(status)

    def proxy_to_backend(self):
        # Strip "/api" so "/api/subscriptions" -> "http://127.0.0.1:8000/subscriptions"
        parsed = self.api_route()
        if parsed is None:
            self.reject_request()
            return

        target_url = BACKEND_URL + parsed.path[4:]
        if parsed.query:
            target_url += "?" + parsed.query
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        req = Request(
            target_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method=self.command,
        )

        try:
            resp = urlopen(req)
            status = resp.status
            resp_body = resp.read() if status != 204 else b""
        except HTTPError as e:
            status = e.status
            resp_body = e.read()
        except URLError:
            status = 502
            resp_body = json.dumps({
                "error": "backend_unreachable",
                "field": "server",
                "message": "Cannot connect to FastAPI at 127.0.0.1:8000. Make sure the backend is running."
            }).encode("utf-8")

        self.send_response(status)
        if status != 204:
            self.send_header("Content-Type", "application/json")
        self.end_headers()

        if status != 204 and resp_body:
            self.wfile.write(resp_body)

    def do_GET(self):
        if self.api_route() is not None:
            self.proxy_to_backend()
        elif urlsplit(self.path).path in ("/", "/index.html"):
            super().do_GET()
        else:
            self.reject_request()

    def do_HEAD(self):
        if urlsplit(self.path).path in ("/", "/index.html"):
            super().do_HEAD()
        else:
            self.reject_request()

    def do_POST(self):
        self.proxy_to_backend()

    def do_PATCH(self):
        self.proxy_to_backend()

    def do_DELETE(self):
        self.proxy_to_backend()


if __name__ == "__main__":
    print(f"Frontend server running at http://127.0.0.1:{PORT}")
    print(f"Forwarding /api/... requests to {BACKEND_URL}")
    HTTPServer(("127.0.0.1", PORT), ProxyHandler).serve_forever()
