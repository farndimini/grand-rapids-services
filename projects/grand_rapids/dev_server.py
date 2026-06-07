import http.server
import json
import os
import re
import sys
import urllib.parse

PORT = int(os.environ.get("PORT", "3000"))
ROOT = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(ROOT, "vercel.json"), encoding="utf-8") as f:
    config = json.load(f)

rewrites = config.get("rewrites", [])

REWRITE_RULES = []
for rule in rewrites:
    src = rule["source"]
    dst = rule["destination"]
    r = re.escape(src)
    r = r.replace(r":match\*", "(.+)")
    r = r.replace(r":slug\*", "(.+)")
    r = r.replace(r":slug", "([^/]+)")
    REWRITE_RULES.append((re.compile("^" + r + "$"), dst))


def find_file(path):
    """Try to find a file for the given URL path."""
    path = path.rstrip("/") or "/"

    # Direct file match
    direct = os.path.join(ROOT, path.lstrip("/"))
    if os.path.isfile(direct):
        return direct

    # Index file for directory
    if os.path.isdir(direct):
        index = os.path.join(direct, "index.html")
        if os.path.isfile(index):
            return index

    # cleanUrls: append .html
    html = os.path.join(ROOT, path.lstrip("/") + ".html")
    if os.path.isfile(html):
        return html

    return None


def resolve(path):
    path = path.rstrip("/") or "/"

    # Try direct file first (before rewrite)
    f = find_file(path)
    if f:
        return f

    # Apply rewrites
    for pat, dst in REWRITE_RULES:
        m = pat.match(path)
        if m:
            new_path = dst
            for i, g in enumerate(m.groups(), 1):
                new_path = new_path.replace(f":match{i}", g)
                new_path = new_path.replace(f":slug{i}", g)
                new_path = new_path.replace(":match*", g)
                new_path = new_path.replace(":slug*", g)
            f = find_file(new_path)
            if f:
                return f
            # Also try with cleanUrls on redirect destination
            f = find_file(new_path.rstrip("/") or "/")
            if f:
                return f
            break

    # Try original path one more time with cleanUrls
    return find_file(path)


MIME = {
    ".html": "text/html; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        f = resolve(p)
        if not f:
            self.send_error(404, f"Not found: {p}")
            return
        ext = os.path.splitext(f)[1].lower()
        try:
            with open(f, "rb") as fp:
                data = fp.read()
            self.send_response(200)
            self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(500, str(e))

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {args[0]} {args[1]} {args[2]}", flush=True)


if __name__ == "__main__":
    import socketserver
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    server = socketserver.ThreadingTCPServer(("", PORT), Handler)
    server.server_activate()
    print(f"Serving at http://localhost:{PORT}", flush=True)
    print(f"Root: {ROOT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped", flush=True)
        server.server_close()
