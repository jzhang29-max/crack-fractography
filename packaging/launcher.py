#!/usr/bin/env python3
"""Entry point for the packaged app: a native window with the analysis inside it.

WHY A WEBVIEW AND NOT A BROWSER TAB. The first version of this started a server and opened
the system browser. That works, but it is not an app: there is no Dock icon that is the
thing you are using, the window is one tab among forty, and quitting the browser does not
quit the program while quitting the program leaves a dead tab behind. pywebview puts the
same page inside a real WKWebView window, so it is an application -- and none of the UI had
to change, because it is the same page served by the same local server.

WHY NOT TKINTER FOR THE UI. The interface is charts, SVG figures and tables. Rebuilding
those in a widget toolkit would be a rewrite of the entire front end to gain nothing.

WHY NOT ELECTRON. It would ship a second browser engine, roughly the size of everything
else here combined. WKWebView is already on the machine.

DOWNLOADS ARE THE ONE THING A WEBVIEW BREAKS. In a browser, "download CSV" is a navigation
that the browser turns into a file. WKWebView has no download manager, so the same
navigation shows the CSV as text or does nothing at all. So the page asks Python instead,
through the js_api below, and gets a real macOS save panel -- which is a better result than
the browser's silent drop into ~/Downloads. See the download() helper in app/static/app.js.

Falls back to the system browser when pywebview is unavailable, so running this from a
checkout still works with nothing extra installed.
"""
import base64
import os
import socket
import sys
import threading
import traceback
import webbrowser

if getattr(sys, "frozen", False):
    sys.path.insert(0, sys._MEIPASS)
else:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import paths as P   # noqa: E402

TITLE = "Crack Fractography"


def log(msg):
    try:
        with open(os.path.join(P.DATA, "launcher.log"), "a") as fh:
            fh.write(str(msg) + "\n")
    except OSError:
        pass
    print(msg, flush=True)


def free_port():
    """Ask the OS rather than guessing. An app cannot hardcode 8810 and let the user
    notice the clash."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def serve(port, ready):
    import uvicorn
    from app.server import app as fastapi_app
    cfg = uvicorn.Config(fastapi_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(cfg)

    def watch():
        import time
        for _ in range(1200):
            if server.started:
                ready.set()
                return
            time.sleep(0.05)
    threading.Thread(target=watch, daemon=True).start()
    server.run()


class Api:
    """Exposed to the page as window.pywebview.api."""

    def __init__(self):
        self.window = None

    def save(self, filename, b64, _text=None):
        """Write a file the page produced, through the OS save panel.

        Returns a short status the page shows, rather than raising: a cancelled save panel
        is a normal outcome and must not surface as a JavaScript error.
        """
        import webview
        try:
            ext = os.path.splitext(filename)[1].lstrip(".") or "*"
            dest = self.window.create_file_dialog(
                webview.FileDialog.SAVE, save_filename=filename,
                file_types=(f"{ext.upper()} (*.{ext})", "All files (*.*)"))
            if not dest:
                return "cancelled"
            dest = dest if isinstance(dest, str) else dest[0]
            with open(dest, "wb") as fh:
                fh.write(base64.b64decode(b64))
            return "saved " + os.path.basename(dest)
        except Exception as e:
            return f"save failed: {type(e).__name__}: {e}"

    def reveal_data(self):
        if sys.platform == "darwin":
            os.system(f"open {P.DATA!r}")
        elif os.name == "nt":
            os.startfile(P.DATA)                                     # noqa: S606
        else:
            os.system(f"xdg-open {P.DATA!r}")
        return P.DATA

    def data_dir(self):
        return P.DATA


def main():
    P.ensure_dirs()
    port = int(os.environ.get("PORT") or 0) or free_port()
    url = f"http://127.0.0.1:{port}"
    ready = threading.Event()

    def boot():
        try:
            serve(port, ready)
        except Exception:
            log("SERVER FAILED TO START\n" + traceback.format_exc())
            ready.set()
    threading.Thread(target=boot, daemon=True).start()

    log(f"{TITLE}\n  address  {url}\n  data     {P.DATA}")
    log(f"  SEM repo {P.sem_repo() or 'not set -- masks you add still measure'}")

    if not ready.wait(timeout=60):
        log("the server did not come up within 60s")

    try:
        import webview
    except ImportError:
        log("pywebview not installed; opening the system browser instead")
        webbrowser.open(url)
        threading.Event().wait()
        return

    api = Api()
    api.window = webview.create_window(TITLE, url, js_api=api,
                                       width=1440, height=940, min_size=(720, 560))
    # Nothing here needs a Chromium; WKWebView is what macOS already has.
    webview.start(gui="cocoa" if sys.platform == "darwin" else None,
                  private_mode=False, storage_path=os.path.join(P.DATA, "webview"))


if __name__ == "__main__":
    main()
