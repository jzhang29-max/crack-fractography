#!/usr/bin/env python3
"""The /mark/ proxy: what it rewrites, what it must NOT rewrite, and what it forwards.

Run against a stub HTTP server rather than the real marking tool. The tool writes into a
hand-labelled paint layer, and a test suite is the last thing that should be pointed at it.
"""
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import mark_proxy as MP  # noqa: E402

#: A stand-in for the tool's UI page, in the shape that matters: a document whose API calls
#: are root-relative string literals.
PAGE = (b"<!doctype html><html><head><title>t</title></head><body><script>\n"
        b"fetch('/api/images');\n"
        b"fetch('/api/retrain', {method:'POST'});\n"
        b"img.src = '/api/thumb/' + n;\n"
        b"</script></body></html>")

#: 12 MB of not-text, to catch a proxy that decodes or re-encodes a binary body.
BLOB = bytes(range(256)) * 48000


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, status, body, ctype):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Upstream-Marker", "kept")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/":
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif p == "/blob.png":
            self._send(200, BLOB, "image/png")
        elif p == "/empty204":
            # EXACTLY what /api/paintlayer does: no content, but Flask still stamps a
            # text/html type on it.
            self._send(204, b"", "text/html; charset=utf-8")
        elif p == "/boom":
            self._send(500, b"<html><body>upstream fell over</body></html>",
                       "text/html; charset=utf-8")
        elif p == "/missing":
            self._send(404, b'{"error":"no template for this image"}', "application/json")
        elif p == "/echoquery":
            self._send(200, self.path.encode(), "text/plain")
        else:
            self._send(404, b"?", "text/plain")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self._send(200, self.rfile.read(n), "application/octet-stream")


def _serve():
    srv = HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


# --- the rewrite itself --------------------------------------------------------------
def test_every_root_relative_api_call_is_pointed_at_mark():
    out, n = MP.rewrite(PAGE.decode())
    assert n == 3
    assert "'/mark/api/images'" in out
    assert "'/mark/api/retrain'" in out
    assert "'/mark/api/thumb/'" in out
    assert "'/api/" not in out, "a leftover root-relative call would hit this app's own API"


def test_a_rewrite_that_matches_nothing_is_an_error_not_a_silent_pass():
    """The failure mode of a string rewrite is silence: the page renders perfectly and every
    button talks to the wrong server. If the tool's HTML is restructured, say so."""
    import pytest
    with pytest.raises(ValueError) as e:
        MP.rewrite("<html><body>no api calls here</body></html>")
    # The message has to name what it looked for, or the next person cannot act on it.
    assert MP.NEEDLE in str(e.value)


# --- WHAT MUST NOT BE REWRITTEN. This is the regression. ------------------------------
def test_a_204_with_an_html_content_type_is_not_the_ui_page():
    """/api/paintlayer answers 204 with an empty body and Content-Type: text/html, because
    Flask stamps its default type on a bodyless response. Keying the rewrite on the content
    type alone turned that correct 204 into a 500 that blamed the tool for having changed
    shape -- which is exactly the wrong direction for a diagnostic to point."""
    assert not MP.is_ui_page(204, b"")


def test_an_upstream_html_error_page_is_not_the_ui_page():
    """It carries no API calls either, so the assertion would fire and replace the tool's
    own error message with a proxy error about rewriting."""
    assert not MP.is_ui_page(500, b"<html><body>upstream fell over</body></html>")


def test_the_real_ui_page_is_the_ui_page():
    assert MP.is_ui_page(200, PAGE)


# --- forwarding ----------------------------------------------------------------------
def test_the_ui_page_comes_through_rewritten():
    srv, port = _serve()
    try:
        status, headers, body, n = MP.forward(port, "/")
        assert status == 200 and n == 3
        assert b"'/mark/api/images'" in body
    finally:
        srv.shutdown()


def test_content_length_is_not_forwarded_because_the_body_grew():
    """Each rewrite adds 5 bytes. Forwarding the upstream's Content-Length would make the
    client truncate the page mid-script -- and it would look like a browser bug."""
    srv, port = _serve()
    try:
        _, headers, body, n = MP.forward(port, "/")
        assert len(body) == len(PAGE) + 5 * n
        assert not [k for k in headers if k.lower() == "content-length"]
        assert headers.get("X-Upstream-Marker") == "kept", "other headers must survive"
    finally:
        srv.shutdown()


def test_a_binary_body_is_byte_identical():
    """A 23 MB PNG goes through this path every time a template is opened."""
    srv, port = _serve()
    try:
        status, _, body, n = MP.forward(port, "/blob.png")
        assert status == 200 and n == 0
        assert body == BLOB
    finally:
        srv.shutdown()


def test_a_204_survives_as_a_204():
    srv, port = _serve()
    try:
        status, _, body, n = MP.forward(port, "/empty204")
        assert (status, body, n) == (204, b"", 0)
    finally:
        srv.shutdown()


def test_an_upstream_error_is_forwarded_verbatim():
    """The tool's own 404s and 409s ARE the answer -- "no template for this image", "a
    reapply job is already running". Turning them into a 502 would replace a usable message
    with a gateway complaint."""
    srv, port = _serve()
    try:
        status, _, body, _ = MP.forward(port, "/missing")
        assert status == 404
        assert b"no template for this image" in body
        status, _, body, _ = MP.forward(port, "/boom")
        assert status == 500 and b"upstream fell over" in body
    finally:
        srv.shutdown()


def test_the_query_string_reaches_the_tool():
    """Cache-busters (?t=...) and thumbnail widths (?w=128) are carried in the query, so
    dropping it would serve a stale template and a full-size thumbnail."""
    srv, port = _serve()
    try:
        _, _, body, _ = MP.forward(port, "/echoquery", query="w=128&t=9")
        assert b"w=128&t=9" in body
    finally:
        srv.shutdown()


def test_a_post_body_reaches_the_tool_unchanged():
    srv, port = _serve()
    try:
        payload = b'{"x":3412,"y":2012,"mode":"toggle"}'
        status, _, body, _ = MP.forward(port, "/anything", method="POST", body=payload,
                                        headers={"Content-Type": "application/json"})
        assert status == 200 and body == payload
    finally:
        srv.shutdown()


def test_a_dead_tool_is_a_connection_error_not_a_crash():
    srv, port = _serve()
    srv.shutdown()
    srv.server_close()
    try:
        MP.forward(port, "/")
    except ConnectionError as e:
        assert str(port) in str(e)
    else:
        raise AssertionError("a tool that is not listening must surface as ConnectionError")


# --- the port override, which is what keeps development off the real paint layer ------
def test_the_port_override_is_read_from_the_environment():
    was = os.environ.get("MARK_PORT")
    try:
        os.environ["MARK_PORT"] = "8791"
        assert MP.port_override() == 8791
        os.environ["MARK_PORT"] = "not a port"
        assert MP.port_override() is None, "garbage must not become a port number"
        del os.environ["MARK_PORT"]
        assert MP.port_override() is None
    finally:
        if was is None:
            os.environ.pop("MARK_PORT", None)
        else:
            os.environ["MARK_PORT"] = was


def test_the_override_is_preferred_over_the_default_port():
    """A development instance points MARK_PORT at a sandbox copy of the paint layer. If the
    default won, a dev run would proxy to the researcher's real tool -- writes into
    hand-labelled data -- while reporting the sandbox port back to the UI."""
    import importlib
    srv = importlib.import_module("app.server")
    was = os.environ.get("MARK_PORT")
    try:
        os.environ["MARK_PORT"] = "8791"
        assert srv._paint_port_candidates()[0] == 8791
    finally:
        if was is None:
            os.environ.pop("MARK_PORT", None)
        else:
            os.environ["MARK_PORT"] = was
