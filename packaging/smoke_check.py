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


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: smoke_check.py <binary> [port]")
    binary = sys.argv[1]
    port = sys.argv[2] if len(sys.argv) > 2 else "8899"
    if not os.path.exists(binary):
        sys.exit(f"no binary at {binary}")

    env = dict(os.environ, PORT=port,
               FRACTOGRAPHY_DATA=os.path.abspath("_smoke_data"))
    log = open("_smoke.log", "wb")
    # No display on a CI runner, so the native window cannot open. The launcher falls back
    # and the server still comes up -- the half this can actually verify.
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
        if not health["capabilities"]["measure_uploaded_mask"]:
            problems.append("cannot measure an uploaded mask, which needs nothing installed")
        if health["measurement_impl"]["source"] != "bundled copy":
            problems.append(f"measurement code came from "
                            f"{health['measurement_impl']['source']!r}; a packaged build "
                            f"with no SEM checkout must use its own bundled copy")
        if problems:
            for p in problems:
                print("FAIL: " + p)
            return 1
        print("OK: starts, serves, and measures with its own bundled code")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
