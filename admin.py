#!/usr/bin/env python3
"""Runs the website's admin panel on your own computer.

    python admin.py

Then open http://localhost:8090/admin/ in your browser (it opens by itself).

Everything you change in the panel is saved straight into the files in content/ and
static/img/, and the site is rebuilt at once so you can look at the result on the same
address (http://localhost:8090/). To put the changes online, upload them to GitHub as
usual (GitHub Desktop: Commit, then Push).

On the live website the same panel is at sunbirdtours.lk/admin/ and saves to GitHub
instead (see README.md). Needs only Python 3.8+ (no extra packages).

    python admin.py 8097 --no-open     another port, and don't open the browser
"""
import base64
import http.server
import json
import mimetypes
import os
import posixpath
import subprocess
import sys
import threading
import time
import webbrowser
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "_site")
PANEL = os.path.join(ROOT, "static", "admin")
# the only folders the panel may change
EDITABLE = ("content/", "static/img/")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif")
MAX_UPLOAD = 25 * 1024 * 1024

build_lock = threading.Lock()
state = {"ok": None, "log": "", "built": 0}


def inquiry_api():
    """The inquiry box's address (inquiry_api in content/settings.txt), so the panel's Inquiries page
    works here too. INQUIRY_API=<address> overrides it, like in build.py."""
    v = os.environ.get("INQUIRY_API", "")
    if not v:
        try:
            with open(os.path.join(ROOT, "content", "settings.txt"), encoding="utf-8") as f:
                for line in f:
                    if line.startswith("inquiry_api:"):
                        v = line.split(":", 1)[1]
        except OSError:
            pass
    v = v.strip()
    return "" if v.lower() in ("off", "no", "0") else v.rstrip("/")


def run_build():
    with build_lock:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "build.py")], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        state.update(ok=r.returncode == 0, log=(r.stdout + r.stderr).strip()[-6000:], built=time.time())
        return dict(state)


def safe_path(rel):
    """The full path of a file the panel is allowed to touch, or None."""
    rel = (rel or "").replace("\\", "/").strip().lstrip("/")
    norm = posixpath.normpath(rel)
    if not norm.startswith(EDITABLE) or ".." in norm.split("/") or ":" in norm:
        return None
    full = os.path.realpath(os.path.join(ROOT, *norm.split("/")))
    base = os.path.realpath(ROOT)
    if not full.startswith(base + os.sep):
        return None
    return full


def tree():
    files = []
    for top in EDITABLE:
        start = os.path.join(ROOT, *top.strip("/").split("/"))
        for folder, dirs, names in os.walk(start):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for n in names:
                if n.startswith(".") or n in ("Thumbs.db", "desktop.ini"):
                    continue
                full = os.path.join(folder, n)
                st = os.stat(full)
                rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
                files.append({"path": rel, "size": st.st_size, "sha": "%d-%d" % (st.st_mtime_ns, st.st_size)})
    files.sort(key=lambda f: f["path"])
    return files


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SITE, **kw)

    def log_message(self, fmt, *args):  # keep the window quiet except for saves
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    # ---------------------------------------------------------------- helpers
    def send_json(self, data, code=200):
        raw = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_UPLOAD * 2:
            raise ValueError("That is too big to save.")
        return self.rfile.read(n) if n else b""

    def local_only(self):
        # a web page on another site must not be able to change the files
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if origin and urlparse(origin).netloc != host:
            self.send_json({"error": "Not allowed from another site."}, 403)
            return False
        if not host.split(":")[0] in ("localhost", "127.0.0.1"):
            self.send_json({"error": "Open the panel on localhost."}, 403)
            return False
        return True

    def translate_path(self, path):
        # the panel itself comes straight from static/admin, so it works even before a build
        p = urlparse(path).path
        if p == "/admin" or p.startswith("/admin/"):
            rest = p[len("/admin"):].lstrip("/") or "index.html"
            full = os.path.realpath(os.path.join(PANEL, *rest.split("/")))
            if full.startswith(os.path.realpath(PANEL)):
                return full
        return super().translate_path(path)

    # ---------------------------------------------------------------- routes
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/admin":
            self.send_response(301)
            self.send_header("Location", "/admin/")
            self.end_headers()
            return
        if u.path == "/admin/config.json":
            return self.send_json({"mode": "local", "inquiry_api": inquiry_api()})
        if not u.path.startswith("/api/"):
            return super().do_GET()
        if not self.local_only():
            return
        q = parse_qs(u.query)
        if u.path == "/api/status":
            return self.send_json({"mode": "local", **state})
        if u.path == "/api/tree":
            return self.send_json({"files": tree()})
        if u.path == "/api/file":
            full = safe_path((q.get("path") or [""])[0])
            if not full or not os.path.isfile(full):
                return self.send_json({"error": "File not found."}, 404)
            with open(full, "rb") as f:
                raw = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(full)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_json({"error": "Unknown address."}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        if not u.path.startswith("/api/") or not self.local_only():
            return self.send_json({"error": "Unknown address."}, 404)
        try:
            if u.path == "/api/build":
                return self.send_json(run_build())
            if u.path == "/api/save":
                data = json.loads(self.read_body().decode("utf-8"))
                files = data.get("files") or []
                # check every path first, so a bad one changes nothing
                plan = []
                for f in files:
                    full = safe_path(f.get("path"))
                    if not full:
                        return self.send_json({"error": "Not allowed to change %s" % f.get("path")}, 400)
                    plan.append((full, f))
                for full, f in plan:
                    if f.get("delete"):
                        if os.path.isfile(full):
                            os.remove(full)
                        continue
                    if "base64" in f:
                        raw = base64.b64decode(f["base64"])
                        if len(raw) > MAX_UPLOAD:
                            return self.send_json({"error": "%s is too big." % f["path"]}, 400)
                    else:
                        raw = f.get("text", "").encode("utf-8")  # line endings exactly as the panel sends them
                    os.makedirs(os.path.dirname(full), exist_ok=True)
                    tmp = full + ".saving"
                    with open(tmp, "wb") as fh:
                        fh.write(raw)
                    os.replace(tmp, full)
                print("Saved: %s" % (data.get("message") or ", ".join(f.get("path") for f in files)))
                result = run_build()
                if not result["ok"]:
                    print(result["log"])
                return self.send_json({"saved": len(plan), "build": result, "files": tree()})
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            return self.send_json({"error": str(e)}, 400)
        self.send_json({"error": "Unknown address."}, 404)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = int(args[0]) if args else 8090
    first = run_build()
    print(first["log"] or "Built the site.")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = "http://localhost:%d/admin/" % port
    print("\nAdmin panel: %s\nThe site:    http://localhost:%d/\nPress Ctrl+C to stop.\n" % (url, port))
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()
