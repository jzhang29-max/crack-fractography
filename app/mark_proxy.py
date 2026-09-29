#!/usr/bin/env python3
"""Serve the SEM repo's marking tool INSIDE this app, under /mark/.

WHY A PROXY AND NOT A LINK. The marking tool is a separate Flask app on its own port. This
app used to hand off to it by URL, which opened the system browser -- so "correct a mask"
left the application the user had just downloaded, and the whole reason for packaging a
desktop app was undone at the one step that matters most. Proxied under /mark/ it is
same-origin with this app's own pages, which means it can be shown in the window itself and
its retrain / reapply / flip / models / export controls work with no cross-origin setup.

THE ONE THING THIS HAS TO GET RIGHT is that the tool's UI is a single 82 KB HTML page whose
every call is a root-relative `fetch('/api/...')` or `img.src = '/api/...'` -- 27 sites, no
absolute origins anywhere except the SVG namespace, no XMLHttpRequest at all. Root-relative
means a <base href> cannot help: a leading slash ignores it. So the HTML is rewritten on the
way through, and ONLY the HTML: the literal `'/api/` becomes `'/mark/api/`. Matching the
opening quote as part of the pattern is what keeps it off prose and off JSON -- it only ever
appears at the start of a JavaScript string literal.

A COUNT IS ASSERTED, NOT HOPED. _rewrite refuses to return a page it changed zero times,
because the failure mode of a string rewrite is silence: the page loads, looks perfect, and
every button 404s against this app's own API instead of the tool's. If the tool's HTML is
ever restructured so the pattern stops matching, the proxy says so on the first request.

WRITES GO WHERE THEY ALWAYS WENT. This adds no write path of its own -- it forwards to the
tool, which owns the paint layer. Developed against a COPY of that layer via the tool's own
SEMCRACK_PAINT_DIR / SEMCRACK_ORIGINAL_DIR overrides, and MARK_PORT below exists so a dev
instance can be pointed at a sandbox without editing code. The paint layer is hand-labelled
research data and this file is not the place to find out whether a proxy corrupts a PNG.
"""
import os
import urllib.error
import urllib.request

#: Requests that can legitimately take minutes: retrain hands back a job id immediately, but
#: process and reapply do their work inline. Long enough not to truncate real work, finite so
#: a wedged tool surfaces as an error rather than a hung window.
TIMEOUT_S = 900

#: Hop-by-hop and length headers must NOT be forwarded: the body may be rewritten (changing
#: its length) and the transfer encoding is this server's business, not the upstream's.
DROP = {"content-length", "transfer-encoding", "connection", "keep-alive",
        "content-encoding", "te", "trailer", "upgrade", "proxy-authorization"}

#: What gets rewritten, and what it becomes. The opening quote is part of the pattern.
NEEDLE = "'/api/"
REPLACEMENT = "'/mark/api/"


def port_override():
    """A paint-tool port set by the environment, or None.

    Exists for two real cases: a researcher who already has the tool open on a non-default
    port, and a development instance pointed at a sandbox copy of the paint layer so this
    proxy can be exercised without writing to irreplaceable labels.
    """
    v = os.environ.get("MARK_PORT")
    try:
        return int(v) if v else None
    except ValueError:
        return None


def is_ui_page(status, body):
    """Is this the tool's own UI document, as opposed to some other text/html reply?

    THE ASSERTION BELOW MUST ONLY APPLY TO THE UI PAGE, and getting that wrong is not
    hypothetical -- it shipped for one test cycle. /api/paintlayer answers 204 No Content
    with an empty body and Content-Type: text/html, because Flask stamps its default type on
    a bodyless response. "Is it HTML?" therefore matched, the rewrite found nothing in the
    empty string, and a perfectly correct 204 came back as a 500 blaming the tool for having
    changed shape. Upstream HTML ERROR pages have the same problem in reverse: they carry no
    API calls either, and turning them into a proxy error would hide the real message.

    So: a 200, with a body, that declares itself a document.
    """
    return status == 200 and bool(body) and b"<html" in body[:4096].lower()


def rewrite(html):
    """Point the tool's root-relative API calls back through /mark/.

    Raises if nothing matched. A rewrite that silently does nothing ships a page whose every
    control talks to the wrong server, and it looks identical to a working one.
    """
    n = html.count(NEEDLE)
    if not n:
        raise ValueError(
            f"the marking tool's page contains no {NEEDLE!r}, so its API calls cannot be "
            "pointed at /mark/. Its HTML has changed shape; this proxy needs updating "
            "rather than bypassing.")
    return html.replace(NEEDLE, REPLACEMENT), n


def forward(port, path, method="GET", body=None, headers=None, query=""):
    """One request through to the tool. Returns (status, headers, body_bytes, n_rewrites).

    n_rewrites is 0 for everything that is not HTML, and non-zero for the UI page -- the
    caller can log it, and the test suite asserts on it.
    """
    url = f"http://127.0.0.1:{port}/{path.lstrip('/')}"
    if query:
        url += "?" + query
    req = urllib.request.Request(url, data=body, method=method)
    for k, v in (headers or {}).items():
        if k.lower() not in DROP and k.lower() != "host":
            req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            status, raw, hdrs = r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        # An upstream 4xx/5xx is an ANSWER, not a proxy failure. Forwarding it verbatim is
        # what lets the tool's own error messages reach the user; turning it into a 502 here
        # would replace "no template for this image" with "bad gateway".
        status, raw, hdrs = e.code, e.read(), dict(e.headers)
    except urllib.error.URLError as e:
        raise ConnectionError(f"the marking tool is not answering on port {port}: {e.reason}")

    n = 0
    if is_ui_page(status, raw):
        text, n = rewrite(raw.decode("utf-8", "replace"))
        raw = text.encode("utf-8")

    out = {k: v for k, v in hdrs.items() if k.lower() not in DROP}
    return status, out, raw, n
