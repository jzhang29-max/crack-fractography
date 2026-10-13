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

    tilebench.py        the one scoring instrument -- LOSO selection, controls, tolerance.
                        Carries both reference points: V147_CLASSIFIER_ON and
                        SHIPPED_V1491, the latter in all five aggregations
    tilebench_verify.py proves the HARNESS reproduces the independently measured v1.47
                        score before anything built on it is believed. It does NOT check
                        the shipped detector: crackpipe is the classifier-on v1.47 path
    crackpipe.py        the v1.47 pipeline (region classifier on, single flattening
                        radius) with its baked-in constants exposed. NOT what ships
    improve/            the six-lever search, its audits, and the safety tests that
                        disqualified both precision rules
    improve/angle4_shipped.py   the v1.49.1 path the app really runs, bound out of
                        detector_overrides.install() so it cannot drift from production
    improve/aggregation.py      the same masks and labels under every legitimate
                        aggregation -- the spread is wider than any model change here
    improve/app_truth.py        checks the scored masks against what the app emits
                        (242 px over 26 tiles, all in the app's favour)
