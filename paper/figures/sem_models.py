"""Stage 1 for figure 2's SEM column: read the two SEM model bundles into a JSON record.

mk_fig2.py used to carry the eight Pass-1 coefficients and the Pass-2 rule constants as
LITERALS in the plate maker, under a docstring saying they had been read out of the shipped
artefacts. They had been, once, by hand. That is exactly the drift this directory's rule
against computing in the plate maker exists to stop: the bundle can be refitted and the
figure will go on drawing last year's weights with no check able to notice. Everything
figure 2 says about the SEM models now comes from here, and from the committed
`sem_models.json` that this writes.

Nothing here is a measurement of the detector -- it is a readout of two files. The
measurements of what the models DO in production are in sem_production.json.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import json, sys
import numpy as np
import joblib

S = _paths.require(_paths.SEM_REPO, "the sem-crack-detector checkout", "SEM_REPO")
P1 = _paths.require(os.path.join(S, "models", "crack_classifier.joblib"),
                    "the Pass-1 region classifier bundle", "SEM_REPO")
P2 = _paths.require(os.path.join(S, "interior_active_learning", "models",
                                 "unified_model.joblib"),
                    "the Pass-2 unified model bundle", "SEM_REPO")

b, u = joblib.load(P1), joblib.load(P2)


def readout(bundle, path):
    clf, names = bundle["clf"], list(bundle["feature_names"])
    coef = np.asarray(clf.coef_).ravel()
    assert len(coef) == len(names), (len(coef), len(names))
    # Sorted by magnitude, which is the order the bar chart draws and therefore the order
    # the caption must quote; sorting in the plate maker would be the plate maker deciding
    # something the record should.
    order = np.argsort(-np.abs(coef))
    return dict(
        path=os.path.relpath(path, S),
        family=type(clf).__name__,
        sklearn_version=bundle.get("sklearn_version"),
        n_features=len(names),
        n_params=len(coef) + 1,
        coefficients=[[names[i], round(float(coef[i]), 4)] for i in order],
        intercept=round(float(np.asarray(clf.intercept_).ravel()[0]), 4),
        class_weight=str(getattr(clf, "class_weight", None)),
        max_iter=int(getattr(clf, "max_iter", 0)),
    )

p1 = readout(b, P1)
p1.update(
    threshold=float(b["threshold"]),
    threshold_provenance=str(b.get("threshold_provenance")),
    n_train=int(b["n_train"]), n_pos=int(b["n_pos"]), n_neg=int(b["n_neg"]),
    n_images=len(b["images"]),
    pooled_auc=float(b["cv_results"]["LogisticRegression"]["pooled_auc"]),
    pooled_auc_sd=float(b["cv_results"]["LogisticRegression"]["pooled_auc_std"]),
    # The family comparison figure 2 draws beside the bar chart, from the same bundle's own
    # cross-validation record rather than from the paper's prose.
    # The keys are `acc` and `spec`. An earlier version of this readout asked for
    # "accuracy"/"specificity", got None for all four families and wrote the Nones to the
    # record without complaint -- so assert the keys rather than tolerate their absence.
    families={k: dict(
        accuracy=round(float(v["acc"]), 4),
        specificity=round(float(v["spec"]), 4),
        recall=round(float(v["recall"]), 4),
        pooled_auc=round(float(v["pooled_auc"]), 4),
        loio_auc_exhaustive_image=round(float(v["loio_auc_exhaustive_image"]), 4))
        for k, v in b["cv_results"].items()},
)

assert all(v["accuracy"] is not None and v["specificity"] is not None
           for v in p1["families"].values()), "the family table went empty"

p2 = readout(u, P2)
rule = u["interior_fill_rule"]
p2.update(
    threshold_default=float(u["threshold_default"]),
    interior_fill_rule={k: (round(float(v), 4) if isinstance(v, (int, float)) else v)
                        for k, v in rule.items()},
)

# Two constants figure 2 draws that are neither a model weight nor a production
# measurement, re-derived here rather than carried over from the old caption.
#
#   * The Frangi range. Both figures said "sigma = 1-6". compute_vesselness passes
#     sigmas=range(sigma_min, sigma_max, 1) with (1, 6), and range(1, 6) STOPS AT 5.
#     The filter runs at five scales, 1 to 5. The caption was off by one scale.
#   * The operator ledger. The caption said "44 of the 142 SEM frame-records carry one".
#     The region-level ledger the box describes is manual_corrections_ledger.csv, and it
#     carries 71 rows over 11 distinct frames. 44 is not in it and no record in these
#     repositories produces it, so it is not quoted any more.
import inspect, pandas as pd
sys.path.insert(0, os.path.join(S, "code"))
import detect_cracks as _dc
_sig = inspect.signature(_dc.compute_vesselness)
_vlo = int(_sig.parameters["sigma_min"].default)
_vhi_exclusive = int(_sig.parameters["sigma_max"].default)
_clean = inspect.signature(_dc.clean_mask)

LEDGER = os.path.join(S, "manual_corrections_ledger.csv")
_led = pd.read_csv(LEDGER)

stages = dict(
    frangi_sigmas=list(range(_vlo, _vhi_exclusive, 1)),
    frangi_label=f"{_vlo}\u2013{_vhi_exclusive - 1}",
    clean_open_radius=int(_clean.parameters["open_radius"].default),
    clean_close_radius=int(_clean.parameters["close_radius"].default),
    clean_min_area_px_default=int(_clean.parameters["min_area_px"].default),
    # run_unified_pipeline's own literal, which is what production passes. It is NOT
    # spelled max(5, 40 // 3) there; that is detect_cracks.main()'s derivation and the
    # two agreeing at 13 is a coincidence of arithmetic, not one call site.
    clean_min_area_px_production=13,
    ledger_path=os.path.relpath(LEDGER, S),
    ledger_rows=int(len(_led)),
    ledger_frames=int(_led["SourceImage"].nunique()),
)

rec = dict(sem_repo_relative=True, pass1=p1, pass2=p2, stages=stages)
out = os.path.join(_paths.FIG_CACHE, "sem_models.json")
json.dump(rec, open(out, "w"), indent=1)
print(json.dumps(rec, indent=1))
print("wrote", out)
