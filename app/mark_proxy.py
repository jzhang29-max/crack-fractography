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

NOTE, IF THAT SANDBOX IS EVER RELIED ON AGAIN: those two variables cover two of the five
directories common.py builds. LABELS_DIR, CANDIDATES_DIR and MODELS_DIR have no override,
and a whole-region flip driven through a "sandboxed" tool still appended a row to the real
labels ledger. Verify containment with `git status` on the tool's own repository, not by
hashing the directory you pointed away from.

WHAT IS REACHABLE ACROSS THE SAME-ORIGIN BOUNDARY, since the answer is not "everything the
tool defines" and the rule is easy to get backwards. app/static/app.js drives the embedded
tool by calling `iframe.contentWindow.loadImage(name)`. That resolves. In the SAME file, in
the SAME scope, `iframe.contentWindow.currentImage` is permanently undefined -- and the only
difference is the declaration keyword. In a classic script (the tool's page is one; no
type=module anywhere in it), a top-level `function` declaration creates a property on the
global object, while a top-level `let`, `const` or `class` creates a binding in the global
DECLARATIVE record, which is not a property of globalThis and cannot be read from another
realm. `function loadImage` is therefore callable from the parent; `let currentImage` is not
readable from it. A sync guarded on reading that variable back would see undefined every
time and reload the tool on every call, which is exactly the bug that shipped for one
iteration. Track state on the parent's side instead.
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

#: The app's --surface-1, written literally into INJECT below as well.
#:
#: NOT interpolated with an f-string: INJECT is a stylesheet, so every one of its CSS
#: blocks is a brace pair and f"" reads them as format fields -- the module raised
#: NameError: name 'display' is not defined on `#side { display: none }` at import. The
#: literal is duplicated instead, and a test asserts all three copies agree: this
#: constant, the hex inside INJECT, and --surface-1 in index.html.
SURFACE_1 = "#1a1a19"

#: Where the injected stylesheet goes. Matched case-insensitively; every HTML document the
#: tool serves has one.
HEAD_CLOSE = "</head>"

#: ONE SIDEBAR, NOT TWO. The tool is a whole application with its own left rail -- brand,
#: drop target, a filterable list of all 154 SEM originals, and a model card -- and
#: embedding it whole put that rail directly beside this app's own frame list. Two image
#: lists, side by side, showing DIFFERENT corpora: the app's was on the txm arm's 71
#: frames while the tool's listed 154 SEM images, and picking in one did nothing to the
#: other. That is not an integration, it is two applications sharing a window.
#:
#: So the tool's rail is hidden and its canvas takes the full width. The app's sidebar
#: becomes the only place an image is chosen, and app.js drives the tool's own
#: loadImage() to follow it -- see syncMarkFrame there. Hidden rather than deleted because
#: the tool's own code still reads #imageList and #imageSelect to track state; removing
#: the nodes would break it, and display:none leaves every one of them addressable.
INJECT = """
<style id="fracto-embed">
  /* The tool's own left rail: this app's sidebar replaces it. */
  #side { display: none !important; }
  /* Its main column was sized against that rail. */
  #main { width: 100% !important; max-width: none !important; margin-left: 0 !important; }
  body { overflow-x: hidden; }

  /* AND NO PANEL CHROME OF ITS OWN. The tool is a standalone application and styles
     itself like one -- its own page background, its own bordered toolbar strip. Nested
     inside this app's pane that reads as a second app in a box, which is what a user
     looking at it said. Flattened so the only visible container is the pane.

     THE BACKGROUND IS A COLOUR, NOT `transparent`, AND color-scheme IS RESTATED.
     `transparent` was the obvious choice and it was wrong: an iframe document gets an
     opaque white canvas from the UA, and color-scheme does NOT cross a document
     boundary -- the app declares `color-scheme: dark` on its own :root, and the framed
     tool still computed `normal`. So the tool's toolbar, whose own background this
     stylesheet had just cleared, showed that white canvas through: a bright strip across
     the top of an otherwise dark window, with a light scrollbar beside it. Exactly the
     "two apps" seam this block exists to remove, reintroduced by the line meant to
     remove it. Naming the surface makes the framed document opaque and self-consistent,
     and color-scheme here is what makes its scrollbars and native controls dark.

     SURFACE_1 must equal --surface-1 in index.html; a test asserts it, because a palette
     change there would otherwise leave this seam behind with nothing to catch it. */
  :root { color-scheme: dark; }
  html, body { background: #1a1a19 !important;  /* == SURFACE_1 */ }
  #top { border: 0 !important; border-radius: 0 !important; background: transparent !important;
         box-shadow: none !important; padding-left: 0 !important; padding-right: 0 !important; }
  #foot { border: 0 !important; background: transparent !important; }
  #canvasWrap { border: 0 !important; border-radius: 0 !important; }
</style>
"""


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
    """Point the tool's root-relative API calls back through /mark/, and hide its own rail.

    Raises if either step finds nothing to do. A rewrite that silently does nothing ships a
    page whose every control talks to the wrong server, and it looks identical to a working
    one; an injection that silently does nothing ships two sidebars.
    """
    n = html.count(NEEDLE)
    if not n:
        raise ValueError(
            f"the marking tool's page contains no {NEEDLE!r}, so its API calls cannot be "
            "pointed at /mark/. Its HTML has changed shape; this proxy needs updating "
            "rather than bypassing.")
    out = html.replace(NEEDLE, REPLACEMENT)

    i = out.lower().rfind(HEAD_CLOSE)
    if i < 0:
        raise ValueError(
            "the marking tool's page has no </head>, so the embed stylesheet cannot be "
            "injected and its sidebar would appear beside this app's own.")
    out = out[:i] + INJECT + out[i:]
    return out, n


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
