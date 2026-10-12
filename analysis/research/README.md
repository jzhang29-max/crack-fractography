# research/

Measurement scripts, kept OUT of the packaged app on purpose.

`packaging/fractography.spec` bundles `analysis/*.py` file by file, so anything left at the
top level ships inside the application. These scripts hardcode absolute paths to this
machine's checkouts of `sem-crack-detector` and the app's data directory, which a built
bundle must never contain -- `test_no_owner_home_path_is_baked_into_the_bundle` fails the
build over it, and rightly: an absolute `/Users/<name>` path in a distributed binary leaks
the build machine's layout. A subdirectory is not bundled, so this is where they live.

The two files the app DOES need at `analysis/` top level are `detect_one.py`, which the
server runs as a subprocess under the detector's own interpreter, and
`detector_overrides.py`, which it imports. Both are free of absolute paths; keep them that
way.

    tilebench.py        the one scoring instrument -- LOSO selection, controls, tolerance
    tilebench_verify.py proves the harness reproduces the shipped score before anything
                        built on it is believed
    crackpipe.py        the shipped pipeline with its baked-in constants exposed
    improve/            the six-lever search, its audits, and the safety tests that
                        disqualified both precision rules
