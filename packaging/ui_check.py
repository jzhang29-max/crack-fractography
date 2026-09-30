#!/usr/bin/env python3
"""Drive the packaged app's real UI in a headless browser and assert it works.

WHY THIS EXISTS. Asked "does Linux work?", the honest answer was: the measurement engine
does -- smoke_check.py uploads a mask and checks the crack count against the published
artifact -- but NOTHING had ever rendered the interface on Linux or Windows. Every UI check
in this project has been me driving a browser against a dev server on macOS. So the answer
was "the server works everywhere, the UI works on my laptop", which is not an answer about
the thing people download.

This runs against a BASE URL, so the same script covers a dev server and an unpacked
release artifact, on any platform, in CI or by hand.

It asserts structure and behaviour, not pixels: a screenshot diff would fail on font
rendering differences between platforms, which is exactly the thing that does not matter
here. What matters is that the page boots, the tabs switch, the frame list is populated,
a measurement renders, and nothing throws.
"""
import json
import os
import sys
import time
import urllib.request
import uuid


def seed(base):
    """Upload one mask so there is something to render. Returns its frame name."""
    import io
    from PIL import Image
    im = Image.new("L", (240, 180), 255)
    for y in range(60, 120):
        for x in range(20, 90):
            im.putpixel((x, y), 0)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    b = uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"ui_check.png\"\r\nContent-Type: image/png\r\n\r\n").encode() \
        + buf.getvalue() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(base + "/api/upload", data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={b}")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read()).get("frame")


def serve(binary, port):
    """Start the packaged app and wait for it, the way smoke_check.py does.

    WHY THIS IS HERE RATHER THAN IN THE WORKFLOW. The first version backgrounded the
    binary from bash -- `PORT=8897 "$BIN" &` -- and waited with curl. That works on macOS
    and Linux and hung on Windows: the step burned its full 180s on the seed upload and
    the server never answered, while smoke_check.py launches the SAME binary on the SAME
    runner without trouble. Rather than debug Git Bash's handling of a windowed exe from
    2,000 miles away, use the launcher that is already proven on all three platforms.
    One code path, no shell in it.
    """
    import subprocess
    env = dict(os.environ, PORT=str(port))
    env.setdefault("FRACTOGRAPHY_DATA", os.path.abspath("_ui_data"))
    log = open("_ui_server.log", "wb")
    proc = subprocess.Popen([binary], env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    for _ in range(120):
        if proc.poll() is not None:
            raise RuntimeError("the app exited during startup; see _ui_server.log")
        try:
            urllib.request.urlopen(base + "/api/health", timeout=3).read()
            return proc, base
        except Exception:
            time.sleep(1)
    proc.terminate()
    raise RuntimeError("the app did not answer /api/health within 120s")


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: ui_check.py <base-url | path-to-binary>")
    arg = sys.argv[1]
    proc = None
    if arg.startswith("http://") or arg.startswith("https://"):
        base = arg.rstrip("/")
    else:
        if not os.path.exists(arg):
            sys.exit(f"no binary at {arg}")
        proc, base = serve(arg, int(sys.argv[2]) if len(sys.argv) > 2 else 8897)
    try:
        return run(base)
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except Exception:
                proc.kill()


def run(base):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright is not installed: pip install playwright && playwright install chromium")

    frame = seed(base)
    print(f"seeded frame: {frame}")
    bad, errors = [], []

    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page(viewport={"width": 1400, "height": 1000})
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        pg.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}")
              if m.type == "error" else None)
        # domcontentloaded, NOT networkidle. networkidle resolves only after 500ms with no
        # requests in flight, which never happens if anything on the page polls -- it held
        # on macOS and Linux by timing luck and timed out at 120s on Windows. The real
        # readiness signal is the elements this check is about, and it waits for those
        # below, so the load condition only has to get the document parsed.
        pg.goto(base + "/", wait_until="domcontentloaded", timeout=120_000)

        # 1. The shell.
        tabs = pg.eval_on_selector_all("#tabs button", "els => els.map(e => e.textContent.trim())")
        if tabs != ["Mark", "Results"]:
            bad.append(f"tabs are {tabs}, expected ['Mark', 'Results']")

        # 2. The frame list is populated with the seeded upload.
        pg.wait_for_selector("#frames tr", timeout=60_000)
        rows = pg.eval_on_selector_all("#frames tr:not(.grp)", "els => els.length")
        if rows < 1:
            bad.append("the frame list is empty after an upload")

        # 3. Results renders a measurement and a figure.
        pg.click("#tabs button[data-tab='results']")
        pg.wait_for_selector("#pane-results:not([hidden])", timeout=60_000)
        pg.wait_for_selector("#figout svg", timeout=120_000)
        strip = pg.inner_text(".strip")
        if "%" not in strip:
            bad.append(f"the strip shows no percentage: {strip!r}")
        # WAIT FOR IT, do not count and hope. The read-out is fetched separately from the
        # figure, so counting straight after the figure appeared raced the render and
        # reported "no statements" for a frame that has one. A timeout here is still a
        # real failure -- it just distinguishes "not yet" from "never".
        try:
            pg.wait_for_selector("#pane-results .ro-line", timeout=30_000)
        except Exception:
            bad.append("no statements rendered on the results page within 30s")
        stmts = pg.eval_on_selector_all("#pane-results .ro-line", "els => els.length")
        measured = pg.eval_on_selector_all("#fsel dt", "els => els.length")
        if measured < 1:
            bad.append("the measurements list is empty")

        # 4. The mask image actually decoded.
        wh = pg.eval_on_selector("#mask", "e => [e.naturalWidth, e.naturalHeight]")
        if not wh or wh[0] < 1:
            bad.append(f"the mask image did not load: {wh}")

        # 5. The limits drawer opens and is populated.
        pg.click("#limitsbtn")
        pg.wait_for_selector("#defs:not([hidden])", timeout=30_000)
        defs = pg.eval_on_selector_all("#defsbody .def", "els => els.length")
        if defs < 1:
            bad.append("the limits drawer opened empty")

        # 6. Mark renders an editable canvas for an uploaded frame.
        pg.click("#tabs button[data-tab='mark']")
        pg.wait_for_selector("#pane-mark:not([hidden])", timeout=30_000)
        # :visible MATTERS HERE. Both containers are always mounted -- that is deliberate,
        # so switching arms does not tear down a live tool -- so a plain "#edcanvas,
        # #markframe" resolves to two elements and Playwright waits on whichever comes
        # first in the DOM, which is the HIDDEN iframe. The assertion is that a drawing
        # surface is ON SCREEN, so it has to say so.
        pg.wait_for_selector("#edcanvas:visible, #markframe:visible", timeout=60_000)
        shown = pg.eval_on_selector_all(
            "#markedit, #marktool",
            "els => els.filter(e => !e.hidden).map(e => e.id)")
        if len(shown) != 1:
            bad.append(f"expected exactly one drawing container visible, got {shown}")

        pg.screenshot(path="ui_check.png", full_page=False)
        br.close()

    hard = [e for e in errors if "favicon" not in e]
    if hard:
        bad += hard
    if bad:
        print("UI CHECK FAILED")
        for b in bad:
            print("  -", b)
        return 1
    print(f"UI OK: tabs={tabs}, {rows} frame row(s), {stmts} statement(s), "
          f"{measured} measurement(s), mask {wh[0]}x{wh[1]}, {defs} limit(s), "
          f"mark={shown[0] if shown else '?'}, no page errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
