#!/usr/bin/env python3
"""Force-download server for the Android APK (bind 0.0.0.0 for Arena preview)."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

MIME = {
    ".apk": "application/vnd.android.package-archive",
    ".zip": "application/zip",
    ".html": "text/html; charset=utf-8",
    ".png": "image/png",
}

ATTACH = {".apk", ".zip"}


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Frame-Options", "ALLOWALL")
        self.send_header("Cache-Control", "no-store")
        path = self.path.split("?", 1)[0]
        ext = os.path.splitext(path)[1].lower()
        if ext in ATTACH:
            name = os.path.basename(path)
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        super().end_headers()

    def guess_type(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in MIME:
            return MIME[ext]
        return super().guess_type(path)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.path = "/index.html"
        return super().do_GET()


if __name__ == "__main__":
    httpd = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    print("APK download http://0.0.0.0:8080/", flush=True)
    httpd.serve_forever()
