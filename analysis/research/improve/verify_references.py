"""Resolve every identifier the manuscript cites and confirm it points at the work named.

This exists because three DOIs in an earlier draft of the reference list were constructed
rather than looked up. Two of them resolved to real but unrelated papers -- a
magnesium-alloy thermal-conductivity study and a plasma-electrolytic-oxidation study -- and
one did not resolve at all. A fabricated identifier that lands on a real paper is the worse
failure, because nothing alerts a reader who follows it.

Run it before every submission. It asks the registries, not a search engine: Crossref for
journal DOIs, DataCite for the Zenodo record, and the arXiv API for preprints. A reference
whose first author or title does not match what the manuscript claims is a hard failure,
not a warning.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
SECT = os.path.join(REPO, "paper/manuscript/sections/70-references.md")
UA = {"User-Agent": "crack-fractography-refcheck/1.0 (mailto:jzhang29@stanford.edu)"}

#: what the manuscript asserts about each identifier. A registry record that disagrees with
#: the surname or a distinctive title word is the failure this script is for.
EXPECT = {
    "10.1038/s41467-021-26565-5": ("Durmaz", "complex microstructure inference"),
    "10.1038/s41524-022-00878-5": ("Stuckner", "pre-trained on a large microscopy"),
    "10.1038/s41592-023-02151-z": ("Maier-Hein", "Metrics reloaded"),
    "10.1038/s41592-023-02150-0": ("Reinke", "metric-related pitfalls"),
    "10.1016/j.rse.2014.02.015": ("Olofsson", "estimating area and assessing accuracy"),
    "10.1016/S0031-3203(99)00055-2": ("Sauvola", "Adaptive document image binarization"),
    "10.1016/S1361-8415(98)80009-1": ("Sato", "multi-scale line filter"),
    "10.1007/BFb0056195": ("Frangi", "Multiscale vessel enhancement"),
    "10.1002/cyto.a.20022": ("Meijering", "neurite tracing"),
    "10.7717/peerj.453": ("van der Walt", "scikit-image"),
    "10.1016/j.inffus.2021.09.018": ("Luengo", "metallographic images"),
    "10.1016/j.actamat.2025.120993": ("Prakash", "ExpertSegmentation"),
    "10.1016/j.apmate.2026.100404": ("Tu", "SAMM"),
    "10.1016/j.surfcoat.2015.11.049": ("Vidal", "chromium electrodeposits"),
    "10.1007/s11837-024-06655-7": ("Ngo", "Fracture Surface Defect"),
    "10.1016/j.matchar.2026.116319": ("Jiao", "Curvature-driven"),
    "10.1016/j.engfailanal.2026.111235": ("Zheng", "quasi-cleavage"),
    "10.1088/1361-6501/adbc08": ("Chen", "Distortion correction"),
    # ASTM registers its standards with Crossref without an author, so the surname check
    # is skipped for this one by passing an empty expectation. The title must still match.
    "10.1520/E0562-19E01": ("", "Determining Volume Fraction"),
}
ARXIV = {
    "2602.04154": ("Lu", "Context Determines Optimal Architecture"),
    "2608.27162": ("Tegetmeyer-Kleine", "Data-efficient crack quantification"),
}
DATACITE = {"10.5281/zenodo.23045328": ("Tian", "Cross-Material Few-Shot Segmentation")}


def _get(url):
    r = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(r, timeout=40) as f:
        return f.read().decode()


def check_crossref(doi, want_author, want_title):
    m = json.loads(_get("https://api.crossref.org/works/"
                        + urllib.parse.quote(doi)))["message"]
    title = " ".join((m.get("title") or [""])[0].split())
    auth = (m.get("author") or [{}])[0].get("family", "")
    ok_a = (not want_author) or (want_author.lower() in auth.lower())
    ok_t = want_title.lower() in title.lower()
    return ok_a and ok_t, f"{auth} | {title[:78]}"


def check_arxiv(aid, want_author, want_title):
    x = _get(f"http://export.arxiv.org/api/query?id_list={aid}")
    t = re.search(r"<entry>.*?<title>(.*?)</title>", x, re.S)
    a = re.findall(r"<author>\s*<name>(.*?)</name>", x, re.S)
    if not t:
        return False, "no entry returned"
    title = " ".join(t.group(1).split())
    ok = (want_title.lower() in title.lower()
          and any(want_author.lower() in n.lower() for n in a))
    return ok, f"{a[0] if a else '?'} | {title[:78]}"


def check_datacite(doi, want_author, want_title):
    at = json.loads(_get("https://api.datacite.org/dois/"
                         + urllib.parse.quote(doi)))["data"]["attributes"]
    title = (at.get("titles") or [{}])[0].get("title", "")
    names = " ".join(c.get("name", "") for c in (at.get("creators") or []))
    ok = want_author.lower() in names.lower() and want_title.lower() in title.lower()
    return ok, f"{names[:30]} | {title[:70]}"


def main():
    text = open(SECT, encoding="utf-8").read()
    bad, n = [], 0
    for doi, (a, t) in EXPECT.items():
        if doi.lower() not in text.lower():
            bad.append(f"{doi} is checked here but NOT CITED in the reference list")
            continue
        n += 1
        try:
            ok, what = check_crossref(doi, a, t)
        except Exception as e:
            ok, what = False, f"{type(e).__name__}: {e}"
        print(f"  {'ok  ' if ok else 'FAIL'}  {doi:42s} {what}")
        if not ok:
            bad.append(f"{doi}: expected {a} / '{t}', registry says {what}")
        time.sleep(0.35)
    for aid, (a, t) in ARXIV.items():
        n += 1
        try:
            ok, what = check_arxiv(aid, a, t)
        except Exception as e:
            ok, what = False, f"{type(e).__name__}: {e}"
        print(f"  {'ok  ' if ok else 'FAIL'}  arXiv:{aid:36s} {what}")
        if not ok:
            bad.append(f"arXiv:{aid}: expected {a} / '{t}', got {what}")
        time.sleep(1.0)
    for doi, (a, t) in DATACITE.items():
        n += 1
        try:
            ok, what = check_datacite(doi, a, t)
        except Exception as e:
            ok, what = False, f"{type(e).__name__}: {e}"
        print(f"  {'ok  ' if ok else 'FAIL'}  {doi:42s} {what}")
        if not ok:
            bad.append(f"{doi}: expected {a} / '{t}', got {what}")

    # an identifier in the reference list that this script does not know about is also a
    # failure: it means a citation was added without being verified
    known = {d.lower() for d in EXPECT} | {d.lower() for d in DATACITE}
    # A DOI is 10.NNNN/suffix and the suffix may contain periods, so a character class
    # that excludes "." captures only "10" and reports every reference as unverified.
    # Match the real shape and strip sentence punctuation from the end.
    for found in re.findall(r"doi:\s*(10\.\d{4,9}/\S+)", text, re.I):
        if found.rstrip(".,;)").lower() not in known:
            bad.append(f"doi:{found} appears in the reference list but is not verified here")
    for found in re.findall(r"arXiv:([0-9.]+)", text):
        if found.rstrip(".") not in ARXIV:
            bad.append(f"arXiv:{found} appears in the list but is not verified here")

    print(f"\n{n} identifiers checked against the registries.")
    if bad:
        print("\nFAILURES:")
        for b in bad:
            print("  -", b)
        sys.exit(1)
    print("every identifier resolves to the work the manuscript names.")


if __name__ == "__main__":
    main()
