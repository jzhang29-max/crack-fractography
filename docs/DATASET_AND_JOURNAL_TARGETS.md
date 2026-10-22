# A public SEM-only benchmark, and where to send this

Searched 2026-10-22 by five parallel agents (repository sweep, literature trail,
challenges/adjacent, journal scope, journal precedent), each finding verified by a second
agent. **Caveat on provenance:** the finder→verifier pairing in the run log could not be
fully reconciled, and my own confirming search was cut off by this turn's web-search
budget. Items below are marked by how well they are actually established.

## 1. Is there a public SEM-only crack benchmark? Essentially no — and that is narrower than it sounds

**The defensible negative result, which belongs in the paper:**

> There is no public **SEM metal/alloy crack pixel-mask** dataset other than the Inconel 718
> folders in Zenodo 23045328.

Not "no public SEM crack masks exist" — those do exist, for ceramics and coatings. The
claim has to carry *metal/alloy* and *cracks* together, and that is where it holds.

**VERIFIED HARD.** One agent did not take the Zenodo record's word for its contents: it
pulled the ZIP64 central directory of `train.zip` by HTTP range request (4,389,010,246
bytes, 30,840 entries), located `class_id.txt` at local-header offset 96,049,044, and
range-fetched and inflated it. `train.zip` holds **21** target folders — the 15 declared
plus six Inconel 718 folders — and the archive root is `trainSemData_swin_384`.

### The one candidate worth chasing

| | |
|---|---|
| **DP800 dual-phase steel, panoramic SEM** | Medghalchi et al., Zenodo **11224127**, paper *Materials & Design* 2024, doi:10.1016/j.matdes.2024.113031 |
| what it has | panoramic SEM of DP800 with ferrite / martensite / **damage** masks |
| why it nearly fits | electron microscopy, a metal, pixel masks, public |
| why it does not quite | "damage" is a **union class**, not cracks alone — it will include voids and decohesion |

*Status: reported by two independent agents, not confirmed by me.* If the damage class can
be split, or if cracks dominate it, this is a genuine second SEM metal benchmark and would
change the paper more than any further work on the method.

### Everything else, and why each fails

| candidate | disqualified because |
|---|---|
| NASA MicroNet EBC-1/2/3 (github.com/nasa/pretrained-microscopy-models) | **ceramic coating**, which you excluded. It is the only crack-mask SEM benchmark with a real maintainer |
| Hot-cracking TIG weld set (BAM) | one agent reports **light microscopy, not SEM** |
| Tungsten thermal-shock SEM cracks (arXiv 2610.03505, ORNL) | **no data repository found**; author contact only |
| `nmc-crack-segmentation-data` | lithium-ion **cathode**, not a metal |
| Ti-6Al-4V fractography, CWRU SDLE | **voids**, not cracks |
| DeepFract, 316L CSCC fractography (SSRN 5012225) | claimed public, **not retrievable** |
| High-chromium cast iron SEM | **phases**, not cracks |
| Al-Mg-Si stress corrosion, CWRU SDLE | **X-ray CT**, weak labels |

## 2. Target journals

**The strongest single finding is a near-exact precedent:** Jiao, *"Curvature-driven
quantification of 2D SEM fracture morphology across metallic materials"*, **Materials
Characterization** 2026, doi:10.1016/j.matchar.2026.116319 — deterministic geometric
quantification of 2D SEM fracture morphology. That is this paper's genre, this paper's
modality, and this year. *Reported by a verifier, not confirmed by me.*

| journal | standing (as reported) | why it fits | the risk |
|---|---|---|---|
| **Materials Characterization** (Elsevier) | SJR 1.29, Q1 | the 2026 Jiao precedent is almost the same genre; SEM measurement methodology is its core | wants a materials conclusion, not only a method |
| **Measurement Science and Technology** (IOP) | JCR Q1 in Eng. Multidisciplinary, Q2 in Instruments & Instrumentation | remit is literally measurement method; a Mar 2025 MST paper does SEM measurement methodology on fatigue cracks | quartile depends which index you count |
| **Measurement** (Elsevier / IMEKO) | Q1 by SJR 0.946 | same remit, broader readership | less microscopy-specific |
| **Engineering Failure Analysis** (Elsevier) | Q1 | verified to publish standalone **training-free** image-measurement method papers, e.g. doi:10.1016/j.engfailanal.2026.111235 | expects a failure case |
| **Journal of Microscopy** (Wiley, RMS) | **Q3** | best topical fit for the metric argument itself | quartile fails your Q1 requirement |
| Ultramicroscopy | JCR may be **Q2**, IF ~2.6 | instrument/measurement methodology | quartile |
| Scientific Data | IF 7.2 | if you release the lab corpus, a Data Descriptor | **two article types only**; not for an argument paper |
| Scientific Reports | Q1, SCIE | safe fallback | no topical community |

**Recommendation: Materials Characterization first, Measurement Science and Technology
second.** MatChar for the precedent and the readership; MST if a reviewer says the paper
is a measurement argument rather than a materials result — because at MST that is the
point rather than the objection.

## 3. The novelty opening the search turned up

Four independent searches for a materials-domain paper applying Maier-Hein-style metric
critique (*Metrics Reloaded*, Nature Methods 2024) returned **zero**. The argument that
overlap scores misstate a materials measurement has not been made in this field.

Read this carefully: the *idea* is owned — Olofsson et al. 2014 set out area-proportion
accounting in remote sensing a decade ago, and this paper already cites it. What appears
unoccupied is the **transfer to materials microscopy with a worked measurement**. That is
a weaker claim than novelty and a stronger one than nothing, and it is the first framing
in this project's prior-art log that has not come back owned outright. State it as
transfer, not invention.
