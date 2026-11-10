from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json

BACKEND_URL = "http://127.0.0.1:8000"
PORT = 3000


class ProxyHandler(SimpleHTTPRequestHandler):
    def proxy_to_backend(self):
        # Strip "/api" so "/api/subscriptions" -> "http://127.0.0.1:8000/subscriptions"
        target_url = BACKEND_URL + self.path[4:]
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
        if self.path.startswith("/api/"):
            self.proxy_to_backend()
        else:
            super().do_GET()

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
