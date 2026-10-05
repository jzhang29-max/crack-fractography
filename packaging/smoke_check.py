#!/usr/bin/env python3
"""Does the packaged binary START, SERVE, and resolve its own measurement code?

A build that produces a binary is not a build that works. This asks the three questions a
green CI check would otherwise be silent about, and it is deliberately the same script on
every platform so a Windows pass means what a macOS pass means.

  usage: smoke_check.py <path-to-binary> [port]
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


# ---------------------------------------------------------------------------------------
#: Bars drawn into the test mask. Separated by more than one pixel so 8-connected labelling
#: cannot merge them, and 6 px thick so none is dismissed as a speck.
TEST_BARS = 4


def _png_bars(path, n=TEST_BARS, size=300):
    """Write an 8-bit greyscale PNG of n separated black bars, using only the stdlib.

    Hand-rolled rather than via Pillow so this check can never be skipped for an
    environment reason. It is the release gate; a gate that opts out is not a gate.
    """
    import struct
    import zlib

    rows = []
    for y in range(size):
        band = size // (n + 1)
        on = any(band * (i + 1) <= y < band * (i + 1) + 6 for i in range(n))
        rows.append(b"\x00" + (b"\x00" if on else b"\xff") * size)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        fh.write(chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 0, 0, 0, 0)))
        fh.write(chunk(b"IDAT", zlib.compress(b"".join(rows), 9)))
        fh.write(chunk(b"IEND", b""))


def _measure_check(port):
    """Upload a mask with a known answer and confirm every view of it agrees."""
    import urllib.request
    import uuid

    base = f"http://127.0.0.1:{port}"
    src = os.path.abspath("_smokeprobe_gated.png")
    _png_bars(src)
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"_smokeprobe_gated.png\"\r\nContent-Type: image/png\r\n\r\n"
            ).encode() + open(src, "rb").read() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        base + "/api/upload", data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            up = json.loads(r.read())
    except Exception as e:
        return [f"uploading a mask failed: {type(e).__name__}: {e}"]
    finally:
        if os.path.exists(src):
            os.remove(src)

    bad = []
    frame = up.get("frame")
    if frame != "_smokeprobe":
        bad.append(f"the _gated suffix was not stripped: frame is {frame!r}")
    if up.get("n_cracks") != TEST_BARS:
        bad.append(f"measured {up.get('n_cracks')} cracks in a mask drawn with {TEST_BARS}")

    def get(pth):
        with urllib.request.urlopen(base + pth, timeout=30) as r:
            return r.status, r.read()

    # THE THREE VIEWS MUST AGREE. v1.3.0 stored the record under one name and its rows and
    # mask file under another, so the frame looked measured while these two were empty.
    try:
        _, raw = get(f"/api/frames?arm=uploads")
        if not any(f.get("frame") == frame for f in json.loads(raw)):
            bad.append(f"frame {frame!r} is not in /api/frames after uploading it")
    except Exception as e:
        bad.append(f"/api/frames failed: {e}")
    try:
        _, raw = get(f"/api/cracks?arm=uploads&frame={frame}")
        n = json.loads(raw).get("n_total")
        if n != TEST_BARS:
            bad.append(f"/api/cracks returned {n} rows for a frame measured at {TEST_BARS}")
    except Exception as e:
        bad.append(f"/api/cracks failed: {e}")
    try:
        st, raw = get(f"/api/mask/uploads/{frame}")
        if st != 200 or not raw.startswith(b"\x89PNG"):
            bad.append(f"/api/mask did not return the mask (status {st})")
    except Exception as e:
        bad.append(f"/api/mask failed: {e}")
    return bad


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: smoke_check.py <binary> [port]")
    binary = sys.argv[1]
    port = sys.argv[2] if len(sys.argv) > 2 else "8899"
    if not os.path.exists(binary):
        sys.exit(f"no binary at {binary}")

    # ASK FOR NO WINDOW; DO NOT ASSUME ONE CANNOT OPEN. This used to read "no display on a
    # CI runner, so the native window cannot open -- the launcher falls back and the server
    # still comes up". That was an assumption, it was never checked, and it is false on
    # windows-latest, which ships WebView2: pywebview started a real window, the runner's
    # non-UI-thread COM access threw ICoreWebView2Controller E_NOINTERFACE in a loop, and
    # this check timed out waiting for /api/health. Intermittently, so it read as a flake.
    # The launcher honours FRACTOGRAPHY_NO_WINDOW by serving and never touching a GUI,
    # which is the half this gate can actually verify, on all three platforms, every time.
    env = dict(os.environ, PORT=port,
               FRACTOGRAPHY_DATA=os.path.abspath("_smoke_data"),
               FRACTOGRAPHY_NO_WINDOW="1")
    log = open("_smoke.log", "wb")
    proc = subprocess.Popen([binary], env=env, stdout=log, stderr=subprocess.STDOUT)

    url = f"http://127.0.0.1:{port}/api/health"
    health = None
    for _ in range(60):
        if proc.poll() is not None:
            break
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                health = json.loads(r.read())
                break
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            time.sleep(2)

    try:
        if health is None:
            print("the app never answered /api/health")
            print(open("_smoke.log", errors="replace").read()[-4000:])
            return 1
        print(json.dumps(health, indent=2))
        problems = []
        if not health.get("frozen"):
            problems.append("frozen is false -- this is not the packaged build")
        if health["measurement_impl"]["source"] != "bundled copy":
            problems.append(f"measurement code came from "
                            f"{health['measurement_impl']['source']!r}; a packaged build "
                            f"with no SEM checkout must use its own bundled copy")

        # ACTUALLY MEASURE SOMETHING. This block used to read
        # health["capabilities"]["measure_uploaded_mask"], which is the literal True in
        # server.py -- an assertion that could not fail, printing "OK: ... and measures"
        # for a build whose upload path was broken. It is the gate that should have caught
        # v1.3.0 shipping a frame whose cracks and mask were unreachable, and it did not.
        #
        # The mask is named with a _gated suffix on purpose: that is the shape this
        # project's own export produces, and stripping it is where the frame record and its
        # crack rows drifted apart.
        problems += _measure_check(port)

        if problems:
            for p_ in problems:
                print("FAIL: " + p_)
            return 1
        print("OK: starts, serves, and measures a known mask end to end")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
