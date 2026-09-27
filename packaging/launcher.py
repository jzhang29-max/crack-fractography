#!/usr/bin/env python3
"""Entry point for the packaged app: start the server, open the page, stay quittable.

A double-clicked .app has no terminal. That changes three things a `./run` script never has
to think about:

  IT NEEDS A WINDOW. Not for the UI -- the UI is the browser page -- but so the process can
  be QUIT. A server with no window and no Dock presence is a process the user can only kill
  from Activity Monitor, and they will not know its name. So there is a small control window
  with the address, the data folder and a Quit button. Tkinter, because it is in the standard
  library: a menu-bar library would add a dependency to solve a four-button problem.

  THE PORT MIGHT BE TAKEN. A checkout can hardcode 8810 and let the user notice the clash.
  An app cannot, so it binds port 0, asks the OS what it got, and reports that.

  ERRORS HAVE NOWHERE TO GO. stderr from a bundled app goes to the system log, which nobody
  reads. Startup failures are shown in the window and written to the data folder.

Run from source with:  python3 packaging/launcher.py
"""
import os
import queue
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

_LOG = queue.Queue()


def log(msg):
    _LOG.put(str(msg))
    try:
        with open(os.path.join(P.DATA, "launcher.log"), "a") as fh:
            fh.write(str(msg) + "\n")
    except OSError:
        pass


def free_port():
    """Ask the OS for a port rather than guessing one. Bound and closed immediately; the
    race with another process grabbing it in between is theoretical and uvicorn would report
    it in the window."""
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
        for _ in range(600):
            if server.started:
                ready.set()
                return
            time.sleep(0.05)
    threading.Thread(target=watch, daemon=True).start()
    server.run()


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

    log(f"Crack Fractography")
    log(f"address    {url}")
    log(f"data       {P.DATA}")
    sem = P.sem_repo()
    log(f"SEM repo   {sem or 'not set -- uploaded masks still work; open Setup on the page'}")

    try:
        window(url, ready)
    except Exception:
        # No display, or tkinter is unavailable in this build. Fall back to running headless
        # and say so, rather than exiting with a GUI traceback nobody sees.
        log("no window available; running headless, stop with Ctrl-C")
        ready.wait(timeout=30)
        webbrowser.open(url)
        threading.Event().wait()


def window(url, ready):
    import tkinter as tk
    from tkinter import scrolledtext

    root = tk.Tk()
    root.title("Crack Fractography")
    root.geometry("560x320")
    root.minsize(420, 240)

    head = tk.Frame(root, padx=14, pady=12)
    head.pack(fill="x")
    tk.Label(head, text="Crack Fractography", font=("Helvetica", 16, "bold")).pack(anchor="w")
    status = tk.Label(head, text="starting...", fg="#666")
    status.pack(anchor="w", pady=(2, 0))

    btns = tk.Frame(root, padx=14)
    btns.pack(fill="x")
    open_btn = tk.Button(btns, text="Open in browser", command=lambda: webbrowser.open(url),
                         state="disabled")
    open_btn.pack(side="left")

    def reveal():
        if sys.platform == "darwin":
            os.system(f'open {P.DATA!r}')
        elif os.name == "nt":
            os.startfile(P.DATA)                                   # noqa: S606
        else:
            os.system(f'xdg-open {P.DATA!r}')
    tk.Button(btns, text="Data folder", command=reveal).pack(side="left", padx=6)

    def quit_now():
        root.destroy()
        os._exit(0)          # the uvicorn thread is not interruptible from here
    tk.Button(btns, text="Quit", command=quit_now).pack(side="right")
    root.protocol("WM_DELETE_WINDOW", quit_now)

    txt = scrolledtext.ScrolledText(root, height=9, font=("Menlo", 11), bg="#f6f6f6",
                                    relief="flat")
    txt.pack(fill="both", expand=True, padx=14, pady=12)
    txt.configure(state="disabled")

    def pump():
        while True:
            try:
                line = _LOG.get_nowait()
            except queue.Empty:
                break
            txt.configure(state="normal")
            txt.insert("end", line + "\n")
            txt.see("end")
            txt.configure(state="disabled")
        root.after(200, pump)
    pump()

    opened = {"done": False}

    def check_ready():
        if ready.is_set():
            status.config(text=f"running at {url}", fg="#0a0")
            open_btn.config(state="normal")
            if not opened["done"]:
                opened["done"] = True
                webbrowser.open(url)
            return
        root.after(150, check_ready)
    check_ready()

    root.mainloop()


if __name__ == "__main__":
    main()
