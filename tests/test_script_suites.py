#!/usr/bin/env python3
"""Run the script-style suites under pytest, so one command runs everything.

test_measure.py and test_probes.py predate pytest here: they print PASS/FAIL lines and
return an exit code. `pytest tests/` collected NOTHING from them -- no test_* function, no
assertion -- and reported success, so the build gate in packaging/build.sh was green while
the two suites that check the actual measurements never ran.

Rather than rewrite 400 lines of working checks into assertions, each suite is invoked as a
subprocess and its exit code is the assertion. Subprocess rather than import because both
call sys.exit and mutate sys.path at module level.
"""
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = ["test_measure.py", "test_probes.py", "test_geodesic.py"]


@pytest.mark.parametrize("suite", SUITES)
def test_script_suite(suite):
    r = subprocess.run([sys.executable, os.path.join(HERE, suite)],
                       capture_output=True, text=True, cwd=os.path.dirname(HERE))
    out = r.stdout + r.stderr
    assert r.returncode == 0, "\n" + "\n".join(
        l for l in out.splitlines() if "FAIL" in l or "Error" in l) + out[-1500:]
    # A suite that prints nothing has passed vacuously, which is how this file came to exist.
    assert "PASS" in out, f"{suite} ran but checked nothing:\n{out[-800:]}"
