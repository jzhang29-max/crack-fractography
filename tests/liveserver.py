#!/usr/bin/env python3
"""Boot a real app server on its own data directory, and drive it over real HTTP.

WHY A SUBPROCESS RATHER THAN A TEST CLIENT. Starlette's TestClient needs httpx, which this
project does not depend on and which would be a runtime dependency added for a test. More
importantly, several of the defects these tests cover only exist in the real server: the
dataset race needs FastAPI's threadpool actually running sync endpoints concurrently, and
a TestClient call is not concurrent with anything.

WHY NOT CALL THE ENDPOINT FUNCTIONS DIRECTLY. Because the repo already has tests that
assert on the SOURCE TEXT of those functions -- checking that a filter contains the right
string -- and an audit's note on one of them was that a source assertion is not a test of
behaviour. These boot the thing and ask it.

Every server gets its own FRACTOGRAPHY_DATA, so nothing here can touch the user's data
directory or the repo's analysis/out.
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    """A live app server on a private data dir. Use as a context manager."""

    def __init__(self, data_dir, seed=None):
        self.data_dir = str(data_dir)
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.seed = seed
        self.proc = None

    def __enter__(self):
        os.makedirs(self.data_dir, exist_ok=True)
        if self.seed:
            import shutil
            for name in ("frames.json", "cracks.json", "specimens.json"):
                src = os.path.join(self.seed, name)
                if os.path.exists(src):
                    shutil.copy(src, os.path.join(self.data_dir, name))
        env = {**os.environ, "FRACTOGRAPHY_DATA": self.data_dir,
               "PYTHONPATH": REPO}
        self.proc = subprocess.Popen(
            [os.path.join(REPO, ".venv", "bin", "python3"), "-m", "uvicorn",
             "app.server:app", "--host", "127.0.0.1", "--port", str(self.port),
             "--log-level", "warning"],
            cwd=REPO, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for _ in range(200):
            if self.proc.poll() is not None:
                out = self.proc.stdout.read().decode()[-2000:]
                raise RuntimeError(f"server exited during startup:\n{out}")
            try:
                self.get("/api/health")
                return self
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("server did not answer within 20s")

    def __exit__(self, *a):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    # --- requests ---------------------------------------------------------------------
    def _send(self, req):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def get(self, path):
        return self._send(urllib.request.Request(self.base + path))

    def post(self, path, body=None, ctype=None):
        req = urllib.request.Request(self.base + path, data=body or b"", method="POST")
        if ctype:
            req.add_header("Content-Type", ctype)
        return self._send(req)

    def upload(self, filename, blob, path="/api/upload", field="file"):
        """multipart/form-data with one file part, hand-rolled so no dependency is added."""
        b = uuid.uuid4().hex
        body = (f"--{b}\r\n"
                f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
                f"Content-Type: image/png\r\n\r\n").encode() + blob + f"\r\n--{b}--\r\n".encode()
        return self.post(path, body, f"multipart/form-data; boundary={b}")

    def json(self, path):
        status, raw = self.get(path)
        return status, (json.loads(raw) if raw else None)

    def dataset(self, name):
        with open(os.path.join(self.data_dir, f"{name}.json")) as fh:
            return json.load(fh)


def mask_png(w=120, h=90, bar=40):
    """A two-valued mask with a black bar `bar` pixels wide. Different bar -> different
    measurement, which is what makes a collision test meaningful."""
    import io

    from PIL import Image
    im = Image.new("L", (w, h), 255)
    for y in range(h // 3, 2 * h // 3):
        for x in range(min(bar, w)):
            im.putpixel((x, y), 0)
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()
