"use strict";
/* Charts are inline SVG built here rather than pulled from a CDN: this app is meant to run on
   a lab machine with no internet, and a chart that silently fails to render is worse than a
   table. Every chart also has a table beside it, which is also what the light-mode contrast
   WARN on two palette slots obliges. */

const $ = (s) => document.querySelector(s);
const state = { arm: null, spec: "", frames: [], frame: null, cracks: null, minArea: 0,
                sortKey: "frame", sortDir: 1 };
const fmt = (v, d = 2) =>
  v === null || v === undefined ? "—"
  : typeof v === "number" ? (Number.isInteger(v) ? v.toLocaleString()
      : v.toLocaleString(undefined, { maximumFractionDigits: d })) : String(v);

async function api(path) {
  const r = await fetch(path);
  if (!r.ok) {
    let msg = `${r.status}`;
    try { msg = (await r.json()).detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return r.json();
}

/* ---------------------------------------------------------------- frames table */
const FCOLS = [
  // SIX columns, down from eleven. The research verdict was blunt: the table was 1109 px
  // against a 512 px card and most of it was not what a materials reader asks first. What
  // survives answers "how much cracking, over how much material, in what units".
  //
  // Cracks and specks COLLAPSE INTO ONE CELL -- they were three columns (n_regions_total,
  // n_cracks_measured, speck_count) telling one story, and the story is the ratio.
  //
  // Everything cut is still in the CSV and in the detail view. Nothing is lost, it is
  // relocated: top1pct_share duplicated largest_share, Orientation_deg was a per-component
  // second moment now superseded by the segment rose, Tortuosity is gone entirely, and
  // MaxWidth is the noisiest number on a 1-3 px crack.
  ["frame", "Frame"],
  ["_cracks", "Cracks"],                       // "457 (+19 specks)"
  ["area_fraction", "Area frac"],
  ["largest_share_of_area", "Largest share"],
  ["p21_skeleton_mm_per_mm2", "P21 mm/mm²"],   // labelled: not a bare "density"
  ["_p10min", "P10 min /mm"],                  // the ASTM B456 criterion is a MINIMUM
];

function renderFrames() {
  const t = $("#frames");
  t.querySelector("thead").innerHTML = "<tr>" + FCOLS.map(([k, l]) =>
    `<th data-k="${k}">${l}${state.sortKey === k ? (state.sortDir > 0 ? " ▲" : " ▼") : ""}</th>`
  ).join("") + "</tr>";
  // Composite cells, derived rather than stored, so the dataset keeps its raw fields.
  const derive = (f) => ({
    ...f,
    _cracks: f.n_cracks_measured,
    _p10min: (f.probe && f.probe.p10_min_per_mm) ?? null,
  });
  const rows = [...state.frames].map(derive).sort((a, b) => {
    const x = a[state.sortKey], y = b[state.sortKey];
    if (x === y) return 0;
    if (x === null || x === undefined) return 1;
    if (y === null || y === undefined) return -1;
    return (x > y ? 1 : -1) * state.sortDir;
  });
  t.querySelector("tbody").innerHTML = rows.map((f) => {
    // A frame with no scale cannot contribute to any physical statistic. Say so in the row
    // rather than showing a blank cell that reads as zero.
    const noScale = f.scale_known ? "" : ` <span class="flag" title="no physical scale established">no scale</span>`;
    return `<tr data-f="${f.frame}" aria-selected="${state.frame === f.frame}">` +
      FCOLS.map(([k]) => {
        if (k === "frame") return `<td title="${f[k]}">${f[k]}${noScale}</td>`;
        if (k === "_cracks") {
          // One cell, because a count without its speck count invites the fragmentation
          // misreading this project has already made once.
          const sp = f.speck_count ? ` <span class="muted">+${f.speck_count.toLocaleString()}</span>` : "";
          return `<td title="${f.n_cracks_measured} measured, ${f.speck_count} specks at or below ${f.speck_threshold_px} px">${fmt(f.n_cracks_measured)}${sp}</td>`;
        }
        return `<td>${fmt(f[k], 4)}</td>`;
      }).join("") + "</tr>";
  }).join("");
  t.querySelectorAll("thead th").forEach((th) => th.onclick = () => {
    const k = th.dataset.k;
    state.sortDir = state.sortKey === k ? -state.sortDir : 1;
    state.sortKey = k; renderFrames();
  });
  t.querySelectorAll("tbody tr").forEach((tr) => tr.onclick = () => selectFrame(tr.dataset.f));
}

/* ---------------------------------------------------------------- rose */
function rose(hist) {
  const el = $("#rose");
  if (!hist || !hist.area_share) { el.innerHTML = `<p class="note">No orientation data.</p>`; return; }
  const R = 108, cx = 150, cy = 130, share = hist.area_share, n = share.length;
  const max = Math.max(...share) || 1;
  // Wedges, 2px gap between neighbours so adjacent fills never touch.
  let p = "";
  share.forEach((v, i) => {
    const a0 = (i * 180 / n - 90) * Math.PI / 180 + 0.012;
    const a1 = ((i + 1) * 180 / n - 90) * Math.PI / 180 - 0.012;
    const r = 14 + (R - 14) * (v / max);
    const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0);
    const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
    p += `<path d="M${cx},${cy} L${x0.toFixed(1)},${y0.toFixed(1)} A${r.toFixed(1)},${r.toFixed(1)} 0 0 1 ${x1.toFixed(1)},${y1.toFixed(1)} Z"
      fill="var(--s1)" fill-opacity="${(0.32 + 0.68 * v / max).toFixed(2)}"
      stroke="var(--surface-2)" stroke-width="2"
      data-tip="${hist.bin_deg[i]}–${hist.bin_deg[i] + 15}°: ${(v * 100).toFixed(1)}% of area"></path>`;
  });
  let ticks = "";
  [0, 45, 90, 135].forEach((d) => {
    const a = (d - 90) * Math.PI / 180;
    ticks += `<text x="${(cx + (R + 14) * Math.cos(a)).toFixed(0)}" y="${(cy + (R + 14) * Math.sin(a)).toFixed(0)}"
      fill="var(--text-muted)" font-size="11" text-anchor="middle" dominant-baseline="middle">${d}°</text>`;
  });
  // Direct-label the dominant bin: selective labels, never one per wedge.
  const top = share.indexOf(max);
  const ta = ((top + 0.5) * 180 / n - 90) * Math.PI / 180;
  const tl = `<text x="${(cx + (R * 0.62) * Math.cos(ta)).toFixed(0)}" y="${(cy + (R * 0.62) * Math.sin(ta)).toFixed(0)}"
    fill="var(--text-primary)" font-size="12" font-weight="600" text-anchor="middle">${(max * 100).toFixed(0)}%</text>`;
  const note = document.querySelector("#rosenote");
  if (note) {
    // Read the weighting off the payload rather than hardcoding it. The caption said
    // "Area-weighted" for a while after the rose became length-weighted, because the word
    // lived in the HTML and the behaviour lived in Python.
    note.textContent = `${hist.weighted_by === "segment length" ? "Length" : hist.weighted_by}-weighted, 15° bins.`;
  }
  el.innerHTML = `<svg viewBox="0 0 300 150" width="100%" role="img"
    aria-label="Length-weighted crack orientation by skeleton branch, 15 degree bins">
    <line x1="${cx - R - 8}" y1="${cy}" x2="${cx + R + 8}" y2="${cy}" stroke="var(--rule)"/>
    ${p}${ticks}${tl}</svg>`;
  wire(el);
}

/* ---------------------------------------------------------------- size distribution */
function sizes(cracks) {
  const el = $("#sizes");
  const areas = cracks.map((c) => c.area_px).filter((a) => a > 0);
  if (!areas.length) { el.innerHTML = `<p class="note">No cracks above the speck threshold.</p>`; return; }
  const lo = Math.log10(Math.min(...areas)), hi = Math.log10(Math.max(...areas));
  const NB = 10, span = (hi - lo) || 1, tot = areas.reduce((a, b) => a + b, 0);
  const bins = Array.from({ length: NB }, () => ({ n: 0, area: 0 }));
  areas.forEach((a) => {
    const i = Math.min(NB - 1, Math.floor((Math.log10(a) - lo) / span * NB));
    bins[i].n++; bins[i].area += a;
  });
  const max = Math.max(...bins.map((b) => b.area / tot)) || 1;
  const W = 300, H = 132, bw = W / NB;
  let bars = "";
  bins.forEach((b, i) => {
    const v = b.area / tot, h = Math.max(v > 0 ? 2 : 0, (H - 26) * (v / max));
    const x = i * bw + 1.5, y = H - 22 - h;
    // 4px rounded data-end, anchored to the baseline.
    bars += `<path d="M${x},${H - 22} L${x},${y + 4} Q${x},${y} ${x + 4},${y}
      L${x + bw - 7},${y} Q${x + bw - 3},${y} ${x + bw - 3},${y + 4} L${x + bw - 3},${H - 22} Z"
      fill="var(--s3)" data-tip="${Math.round(10 ** (lo + i * span / NB)).toLocaleString()}–${Math.round(10 ** (lo + (i + 1) * span / NB)).toLocaleString()} px²: ${(v * 100).toFixed(1)}% of area, ${b.n} regions"></path>`;
  });
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img"
    aria-label="Share of crack area by region size, log-spaced bins">
    <line x1="0" y1="${H - 22}" x2="${W}" y2="${H - 22}" stroke="var(--rule)"/>
    ${bars}
    <text x="0" y="${H - 7}" fill="var(--text-muted)" font-size="11">${Math.round(10 ** lo).toLocaleString()} px²</text>
    <text x="${W}" y="${H - 7}" fill="var(--text-muted)" font-size="11" text-anchor="end">${Math.round(10 ** hi).toLocaleString()} px²</text>
  </svg>`;
  wire(el);
}

function wire(root) {
  const tip = $("#tip");
  root.querySelectorAll("[data-tip]").forEach((n) => {
    n.onmousemove = (e) => {
      tip.textContent = n.dataset.tip; tip.style.opacity = 1;
      tip.style.left = Math.min(e.clientX + 12, innerWidth - tip.offsetWidth - 8) + "px";
      tip.style.top = (e.clientY + 14) + "px";
    };
    n.onmouseleave = () => tip.style.opacity = 0;
  });
}

/* ---------------------------------------------------------------- frame detail */
const CCOLS = [["crack_id", "ID"], ["area_px", "Area px"], ["SkeletonLength_px", "Length px"],
  ["MeanWidth_px", "Mean W"], ["length_is_censored", "Censored"], ["area_um2", "Area µm²"]];

async function selectFrame(name) {
  state.frame = name;
  const f = state.frames.find((x) => x.frame === name);
  renderFrames();
  $("#fsel-title").textContent = name;
  $("#fsel-note").textContent = f.scale_known
    ? `${f.nm_per_px} nm/px — physical units available.`
    : `No physical scale established for this frame; µm columns are empty by design.`;
  const pr = f.probe || {};
  $("#fsel").innerHTML = [
    ["Cracks", `${fmt(f.n_cracks_measured)} <span class="muted">+${fmt(f.speck_count)} specks ≤${f.speck_threshold_px}px</span>`],
    ["Crack area fraction", (f.area_fraction * 100).toFixed(3) + "%"],
    ["Largest region's share", f.largest_share_of_area === null ? "—"
      : (f.largest_share_of_area * 100).toFixed(1) + "%"],
    ...(f.area_analysed_mm2 ? [["Area analysed", fmt(f.area_analysed_mm2, 4) + " mm²"]] : []),
    ...(f.p21_skeleton_mm_per_mm2 ? [["P21 (skeleton)", fmt(f.p21_skeleton_mm_per_mm2, 3) + " mm/mm²"]] : []),
    ...(pr.p21_buffon_mm_per_mm2 ? [["P21 (Buffon)", fmt(pr.p21_buffon_mm_per_mm2, 3) +
        ` mm/mm² <span class="muted">${Math.round(100 * Math.abs(pr.p21_buffon_mm_per_mm2 - f.p21_skeleton_mm_per_mm2) / f.p21_skeleton_mm_per_mm2)}% apart — skeletonisation error</span>`]] : []),
    ...(pr.p10_min_per_mm ? [["P10 min", `${fmt(pr.p10_min_per_mm, 1)} /mm <span class="muted">at ${pr.p10_min_at_deg}°, mean ${fmt(pr.p10_mean_per_mm, 1)}</span>`]] : []),
    ...(f.p20_per_mm2 ? [["P20", fmt(f.p20_per_mm2, 0) + " /mm²"]] : []),
    // MCL is reported as a BRACKET, not a value. Keeping edge-censored regions biases it
    // down (a crack leaving the frame is longer than the part seen); dropping them biases
    // it up (long cracks reach edges more often). Both ends, or neither.
    ...(f.mcl_um ? [["Longest crack (MCL)",
      f.mcl_um_uncensored_only != null && f.mcl_censored
        ? `${fmt(f.mcl_um, 1)} µm <span class="muted">censored — ${fmt(f.mcl_um_uncensored_only, 1)} µm if edge-touching cracks are dropped</span>`
        : `${fmt(f.mcl_um, 1)} µm <span class="muted">${f.mcl_censored === false ? "does not touch an edge" : ""}</span>`]] : []),
    ...(f.tcl_um ? [["Total length (TCL)", fmt(f.tcl_um, 0) + " µm"]] : []),
    ["R_L median", f.R_L_median === null || f.R_L_median === undefined ? "—"
      : `${fmt(f.R_L_median, 3)} <span class="muted">axis ${f.R_L_axis_deg}°, ${fmt(f.R_L_n_segments)} segments</span>`],
    ["Junctions", `${fmt(f.n_junctions)} <span class="muted">${fmt(f.n_triple)} triple, ${fmt(f.n_quadruple_plus)} quad+</span>`],
    ["Touching frame edge", f.censored_share === null ? "—"
      : `${(f.censored_share * 100).toFixed(1)}% <span class="muted">length censored</span>`],
    ["Below 10px width envelope", f.width_below_validated_envelope_share === null ? "—"
      : `${(f.width_below_validated_envelope_share * 100).toFixed(0)}% <span class="muted">of regions</span>`],
    // Cleaning, recorded per frame. The speck threshold is per frame now -- max of a pixel
    // floor (is a shape measurable) and a physical one (did two frames exclude the same
    // class of object) -- so which floor bound is part of the reading.
    ...(f.speck_threshold ? [["Speck floor",
      `${f.speck_threshold_px} px <span class="muted">${f.speck_threshold.binding_floor} floor` +
      `${f.speck_threshold.threshold_um2 ? ` · ${f.speck_threshold.threshold_um2} µm²` : ""}</span>`]] : []),
    ...(f.detection_limit && f.detection_limit.min_resolvable_width_um ? [["Cannot resolve below",
      `${fmt(f.detection_limit.min_resolvable_width_um, 3)} µm <span class="muted">one pixel — narrower cracks are unresolved, not absent</span>`]] : []),
  ].map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");

  // Ingest assertion. Silent when the mask is what it claims to be, and loud when it is
  // not: an inverted mask measures the matrix, reports it as crack, and looks plausible.
  const ing = f.ingest;
  $("#fsel-note").innerHTML = ($("#fsel-note").textContent || "") +
    (ing && ing.warnings && ing.warnings.length
      ? ing.warnings.map((w) => `<br><span class="flag bad">⚠ ${w}</span>`).join("")
      : "");

  $("#mask").hidden = false;
  $("#mask").src = `/api/mask/${state.arm}/${encodeURIComponent(name)}`;
  $("#mask").alt = `Crack mask for ${name}`;
  $("#masknote").textContent = `${state.arm} — black is crack.`;

  rose(f.orientation_hist_deg);
  try {
    const d = await api(`/api/cracks?frame=${encodeURIComponent(name)}&arm=${encodeURIComponent(state.arm)}`);
    state.cracks = d;
    renderCracks();
  } catch (e) { $("#cracknote").textContent = "Could not load cracks: " + e.message; }
}

function renderCracks() {
  const d = state.cracks;
  if (!d) return;
  const rows = d.cracks.filter((c) => c.area_px >= state.minArea);
  // Say what the cap dropped. A silent top-N makes a 5000-crack frame look like a 2000-crack one.
  $("#cracknote").textContent =
    `${rows.length.toLocaleString()} shown of ${d.n_total.toLocaleString()} measured` +
    (d.truncated ? ` — the API capped the response at ${d.n_returned.toLocaleString()}, sorted by ${d.sorted_by}` : "") +
    (state.minArea > 0 ? ` · filtered to ≥ ${state.minArea.toLocaleString()} px` : "");
  const t = $("#cracks");
  t.querySelector("thead").innerHTML = "<tr>" + CCOLS.map(([, l]) => `<th>${l}</th>`).join("") + "</tr>";
  t.querySelector("tbody").innerHTML = rows.slice(0, 400).map((c) => "<tr>" +
    CCOLS.map(([k]) => `<td>${typeof c[k] === "boolean" ? (c[k] ? "yes" : "") : fmt(c[k], 3)}</td>`).join("") +
    "</tr>").join("");
  sizes(rows);
}

/* ---------------------------------------------------------------- boot */
// ---------------------------------------------------------------------------------------
// Setup. A checkout finds the sibling repos through relative symlinks; a downloaded app has
// none, so on first launch there is no SEM repo and no dataset. That is a normal state, not
// an error, and the panel says what already works rather than what is broken: measuring a
// mask you drop on the page needs nothing configured at all.
let HEALTH = null;

async function health() {
  HEALTH = await api("/api/health");
  const c = HEALTH.capabilities;
  $("#caps").innerHTML = [
    [c.measure_uploaded_mask, "Measure a mask you add"],
    [c.segment_raw_micrograph, "Segment a raw micrograph (.tif)"],
    [c.reference_corpus, "The reference corpus"],
  ].map(([on, t]) => `<li class="${on ? "" : "off"}">${t}</li>`).join("");
  $("#sempath").value = HEALTH.sem_repo || "";
  $("#corpusrow").hidden = !c.reference_corpus || HEALTH.corpus_measured;
  const impl = HEALTH.measurement_impl || {};
  // Drift between the app's bundled copy of the shared measurement code and the repo's own
  // is not an error -- the repo wins -- but it means a packaged build would measure
  // differently, so it is said out loud instead of found later as an unexplained gap.
  $("#semmsg").innerHTML = impl.drift
    ? `<span class="flag">measuring with the SEM repo's code, which differs from this app's copy</span>`
    : "";
  return HEALTH;
}

function showSetup(on) { $("#setup").hidden = !on; }

async function wireSetup() {
  $("#setupbtn").onclick = () => showSetup($("#setup").hidden);

  $("#semset").onclick = async () => {
    const v = $("#sempath").value.trim();
    if (!v) return;
    $("#semmsg").textContent = "checking…";
    try {
      const r = await fetch("/api/config?sem_repo=" + encodeURIComponent(v), { method: "POST" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || r.statusText);
      await health();                       // health() rewrites #semmsg, so say it after
      $("#semmsg").textContent = "set";
    } catch (e) { $("#semmsg").innerHTML = `<span class="flag bad">${e.message}</span>`; }
  };

  $("#measure").onclick = async () => {
    $("#measure").disabled = true;
    $("#setuplog").hidden = false;
    const r = await fetch("/api/measure_corpus?arm=all", { method: "POST" });
    if (!r.ok) {
      $("#setuplog").textContent = (await r.json()).detail || r.statusText;
      $("#measure").disabled = false;
      return;
    }
    const poll = async () => {
      const j = await api("/api/measure_corpus");
      $("#setuplog").textContent = j.log.join("\n") || `running… ${j.elapsed_s}s`;
      $("#setuplog").scrollTop = $("#setuplog").scrollHeight;
      if (j.state === "running") return setTimeout(poll, 1500);
      $("#measure").disabled = false;
      if (j.state === "done") location.reload();
    };
    poll();
  };
}

// ---------------------------------------------------------------------------------------
// Downloading, in a browser and in the app window.
//
// `location.href = url` is how a browser downloads a Content-Disposition response, and it
// is exactly what a WKWebView cannot do: there is no download manager behind it, so the
// same navigation shows the CSV as text or silently does nothing. In the app the bytes are
// handed to Python, which opens the real macOS save panel -- a better outcome than the
// browser's silent drop into ~/Downloads, and the only one that works at all.
//
// Detected by capability, not by user agent.
async function download(url, filename) {
  const native = window.pywebview && window.pywebview.api && window.pywebview.api.save;
  if (!native) { location.href = url; return; }
  const note = $("#armnote");
  const prev = note.textContent;
  note.textContent = "preparing " + filename + "…";
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    const buf = new Uint8Array(await r.arrayBuffer());
    let bin = "";
    for (let i = 0; i < buf.length; i += 0x8000) {
      bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
    }
    note.textContent = await window.pywebview.api.save(filename, btoa(bin));
  } catch (e) {
    note.innerHTML = `<span class="flag bad">${e.message}</span>`;
  }
  setTimeout(() => { if (note.textContent !== prev) note.textContent = prev; }, 4000);
}

// ---------------------------------------------------------------------------------------
// Specimen card. First on the page, because the specimen is the inferential unit: frames
// within one are not independent, so a per-frame statistic is pseudo-replication.
//
// The interval is ASTM E562's -- t(0.975, n-1)*s/sqrt(n) over the between-FIELD variance --
// and %RA is E562's own headline, the interval as a share of the mean. The usual target is
// 10%. Nothing in this corpus is close, which is the single most useful thing the card
// says: with the fields measured, area fraction cannot rank these specimens, and the fix
// is more fields rather than more decimal places.
const pct = (v, d = 2) => v == null ? "—" : (100 * v).toFixed(d) + "%";
const num = (v, d = 1) => v == null ? "—" : (+v).toFixed(d);

function raBadge(ci) {
  if (!ci || ci.pct_relative_accuracy == null) return "";
  const v = ci.pct_relative_accuracy;
  return `<span class="ra${v > 10 ? " bad" : ""}" title="ASTM E562 relative accuracy: the 95% interval as a percentage of the mean. The usual target is 10% or better; above it, the answer is more fields, not more decimals.">±${v}%</span>`;
}

function specimenCard(r) {
  const ci = r.area_fraction_ci;
  const scaled = r.scale_known_frames > 0;
  const off = scaled ? "" : ' class="off"';
  const ds = r.detector_sensitivity, as = r.arm_sensitivity;
  const dets = Object.entries(r.detectors || {}).map(([k, v]) => `${k} ${v}`).join(" · ");
  const rows = [
    ["Crack area fraction",
     ci ? `<span class="big">${pct(ci.mean)}</span> <span class="ci">95% CI ${pct(ci.ci95_lo)}–${pct(ci.ci95_hi)}, ${ci.n_fields} fields</span>${raBadge(ci)}`
        : `<span class="big">${pct(r.area_fraction_median)}</span> <span class="ci">median of ${r.n_fields} field${r.n_fields > 1 ? "s" : ""} — under 3, no interval</span>`],
    ["P10", `${num(r.p10_min_per_mm)} <span class="u">/mm min</span> · ${num(r.p10_mean_per_mm)} <span class="u">/mm mean</span>`],
    ["P21 · P20", `${num(r.p21_skeleton_mm_per_mm2)} <span class="u">mm/mm²</span> · ${num(r.p20_per_mm2, 0)} <span class="u">/mm²</span>`],
    // null / 1000 is 0 in JavaScript, so an unscaled specimen was reporting "0.00 mm" of
    // total crack length -- a measured zero where the truth is "not measurable".
    ["MCL · TCL", `${num(r.mcl_um)} <span class="u">µm</span> · ${num(r.tcl_um_total == null ? null : r.tcl_um_total / 1000, 2)} <span class="u">mm</span>`],
  ];
  const extra = [
    ["Detector", `${dets}${ds ? ` · CBS/ETD <b>×${ds.cbs_over_etd_median}</b> <span class="u">on ${ds.n_fields_both_detectors} field${ds.n_fields_both_detectors > 1 ? "s" : ""} imaged both ways</span>` : ""}`],
  ];
  if (as) extra.push(["Gated / machine", as.n_frames_corrected
    ? `<b>×${as.gated_over_machine_where_corrected}</b> <span class="u">where corrected — ${as.n_frames_corrected} of ${as.n_paired_frames} frames</span>`
    : `<span class="u">no corrections on these ${as.n_paired_frames} frames — the two arms are the same mask</span>`]);
  // "over N frames" was wrong next to an area summed over FIELDS -- it named the larger
  // number beside the smaller quantity, which is how the double-count read as plausible.
  extra.push(["Analysed", scaled
    ? `${num(r.area_analysed_mm2, 3)} <span class="u">mm² over ${r.n_fields_scaled ?? r.n_fields} field${(r.n_fields_scaled ?? r.n_fields) > 1 ? "s" : ""}</span>`
    : `<span class="u">no physical scale — µm and mm rows withheld</span>`]);

  return `<dl class="spec">` +
    rows.map(([k, v]) => `<dt>${k}</dt><dd${k === "Crack area fraction" ? "" : off}>${v}</dd>`).join("") +
    extra.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("") + `</dl>`;
}

function specimenTable(rows) {
  // All specimens: the comparison view. Six columns, sorted by the mean it is ranking on.
  const body = rows.slice().sort((a, b) =>
    ((b.area_fraction_ci || {}).mean ?? b.area_fraction_median) -
    ((a.area_fraction_ci || {}).mean ?? a.area_fraction_median)).map((r) => {
    const ci = r.area_fraction_ci, ds = r.detector_sensitivity, as = r.arm_sensitivity;
    return `<tr data-spec="${r.specimen}"><td title="${r.specimen}">${r.specimen}</td>` +
      `<td>${r.n_fields}<span class="u">${r.n_frames !== r.n_fields ? ` /${r.n_frames}f` : ""}</span></td>` +
      `<td>${pct(ci ? ci.mean : r.area_fraction_median)}</td>` +
      `<td>${ci ? `${pct(ci.ci95_lo)}–${pct(ci.ci95_hi)}` : "<span class='u'>n&lt;3</span>"}</td>` +
      `<td>${ci ? raBadge(ci) : "—"}</td>` +
      `<td>${ds ? "×" + ds.cbs_over_etd_median : "—"}</td>` +
      `<td title="${as ? as.n_frames_corrected + " of " + as.n_paired_frames + " frames carry a correction" : ""}">${as ? (as.n_frames_corrected ? "×" + as.gated_over_machine_where_corrected : "<span class='u'>none</span>") : "—"}</td></tr>`;
  }).join("");
  return `<div class="scroll"><table id="spectable"><thead><tr>` +
    `<th>Specimen</th><th title="Fields, and frames where they differ. A field imaged through two detectors is ONE field.">Fields</th>` +
    `<th>Area frac</th><th title="ASTM E562, between-field variance">95% CI</th>` +
    `<th title="Interval as a share of the mean. Target 10%.">±</th>` +
    `<th title="Same physical field, two detectors. Away from 1 is instrument, not material.">CBS/ETD</th>` +
    `<th title="Same frames, operator strokes vs detector alone.">G/M</th>` +
    `</tr></thead><tbody>${body}</tbody></table></div>`;
}

async function renderSpecimens() {
  const card = $("#speccard");
  let rows;
  try { rows = await api(`/api/specimens?arm=${encodeURIComponent(state.arm)}`); }
  catch (e) { card.hidden = true; return; }
  card.hidden = false;
  const one = state.spec ? rows.find((r) => r.specimen === state.spec) : null;
  if (one) {
    $("#specnote").textContent = `${one.specimen} · ${one.n_fields} fields`;
    $("#specbody").innerHTML = specimenCard(one);
  } else {
    const withCI = rows.filter((r) => r.area_fraction_ci);
    const meeting = withCI.filter((r) => r.area_fraction_ci.pct_relative_accuracy <= 10);
    $("#specnote").innerHTML = withCI.length
      ? `${rows.length} specimens · <span class="${meeting.length ? "" : "flag"}">${meeting.length} of ${withCI.length} reach ASTM E562's 10% relative accuracy</span>`
      : `${rows.length} specimens`;
    $("#specbody").innerHTML = specimenTable(rows);
    $("#spectable").querySelectorAll("tbody tr").forEach((tr) => {
      tr.onclick = () => { $("#spec").value = state.spec = tr.dataset.spec; loadArm(); };
    });
  }
}

async function loadArm() {
  try {
    state.frames = await api(`/api/frames?arm=${encodeURIComponent(state.arm)}` +
      (state.spec ? `&specimen=${encodeURIComponent(state.spec)}` : ""));
  } catch (e) { $("#hdr").innerHTML = `<span class="flag bad">${e.message}</span>`; return; }
  // The specimen list comes from the specimen table, not from the frames just fetched:
  // those are already filtered to one specimen, so deriving the options from them left the
  // dropdown reading "all (1 specimens)" with no way back to the rest.
  let specs;
  try {
    specs = (await api(`/api/specimens?arm=${encodeURIComponent(state.arm)}`))
      .map((r) => r.specimen).sort();
  } catch (e) { specs = [...new Set(state.frames.map((f) => f.specimen))].sort(); }
  const cur = state.spec;
  $("#spec").innerHTML = `<option value="">all (${specs.length} specimens)</option>` +
    specs.map((s) => `<option${s === cur ? " selected" : ""}>${s}</option>`).join("");
  const noScale = state.frames.filter((f) => !f.scale_known).length;
  $("#armnote").textContent = noScale
    ? `${noScale}/${state.frames.length} frames: no scale, µm withheld`
    : `all ${state.frames.length} frames scaled`;
  renderFrames();
  renderSpecimens();
  if (typeof window.figRenderRef === "function") window.figRenderRef();
  if (state.frames.length) selectFrame(state.frames[0].frame);
}

(async function () {
  $("#theme").onclick = () => {
    const d = document.documentElement;
    d.dataset.theme = d.dataset.theme === "dark" ? "light" : "dark";
  };
  $("#csv").onclick = () => download(
    `/api/export.csv?arm=${encodeURIComponent(state.arm)}&level=frames`,
    `${state.arm.replace("/", "_")}_frames.csv`);
  // Upload. A .tif is segmented here first; a .png is taken as a mask already. The control
  // says "image or mask" rather than explaining the difference, because the server decides
  // from the extension and the user should not have to.
  $("#up").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const lbl = document.querySelector(".upload");
    const was = lbl.textContent;
    lbl.setAttribute("aria-busy", "true");
    lbl.textContent = /\.tiff?$/i.test(f.name) ? "segmenting…" : "measuring…";
    const fd = new FormData();
    fd.append("file", f);
    try {
      const r = await fetch("/api/upload", { method: "POST", body: fd });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || r.status);
      state.arm = "uploads"; state.spec = "";
      const arms = await api("/api/arms");
      $("#arm").innerHTML = arms.map((a) =>
        `<option value="${a.arm}"${a.arm === "uploads" ? " selected" : ""}>${a.arm} — ${a.n_frames} frames, ${a.n_cracks.toLocaleString()} cracks</option>`).join("");
      await loadArm();
      selectFrame(d.frame);
      lbl.textContent = was;
      $("#armnote").textContent =
        `${d.frame}: ${d.n_cracks.toLocaleString()} cracks, ${d.n_specks.toLocaleString()} specks — ${d.note}` +
        (d.scale_known ? "" : " · no scale, so µm is withheld");
    } catch (err) {
      lbl.textContent = was;
      $("#armnote").innerHTML = `<span class="flag bad">upload failed: ${err.message}</span>`;
    } finally {
      lbl.removeAttribute("aria-busy");
      e.target.value = "";
    }
  };

  $("#minarea").oninput = (e) => {
    state.minArea = +e.target.value;
    $("#minareaval").textContent = state.minArea.toLocaleString();
    renderCracks();
  };
  // --- figure builder ------------------------------------------------------------------
  // The field list comes from the server so the menu can never offer a quantity the
  // renderer does not know, and so "needs a scale" is stated by the same code that
  // enforces it.
  let FIG = null;
  window.figRenderRef = null;
  const figRender = async () => {
    const out = $("#figout");
    if (!FIG || !state.arm) return;
    const kind = $("#figkind").value, y = $("#figy").value, x = $("#figx").value;
    $("#figxwrap").hidden = kind !== "scatter";
    const q = new URLSearchParams({ arm: state.arm, kind, y });
    if (kind === "scatter") q.set("x", x);
    if ($("#figthin").checked) q.set("include_thin", "true");
    out.innerHTML = `<p class="note">drawing…</p>`;
    const r = await fetch(`/api/figure.svg?${q}`);
    if (!r.ok) {
      let d = {}; try { d = await r.json(); } catch (_) {}
      out.innerHTML = `<p class="note"><span class="flag">${d.detail || "could not draw this"}</span></p>`;
      return;
    }
    out.innerHTML = await r.text();
    $("#figdl").onclick = () => {
      q.set("download", "true");
      download(`/api/figure.svg?${q}`,
               `${state.arm.replace("/", "_")}_${q.get("kind")}_${q.get("y") || q.get("x")}.svg`);
    };
  };
  window.figRenderRef = figRender;
  try {
    FIG = await api("/api/figure/fields");
    const opts = FIG.fields.map((f) =>
      `<option value="${f.key}">${f.label}${f.unit ? " (" + f.unit + ")" : ""}${f.needs_scale ? " ·needs scale" : ""}</option>`).join("");
    $("#figy").innerHTML = opts;
    $("#figx").innerHTML = opts;
    $("#figy").value = "area_fraction";
    $("#figx").value = "n_cracks_measured";
    $("#figkind").innerHTML = FIG.kinds.map((k) =>
      `<option value="${k}">${k.replace(/_/g, " ")}</option>`).join("");
    $("#figkind").value = "box_by_specimen";
    ["figkind", "figy", "figx", "figthin"].forEach((id) => $("#" + id).onchange = figRender);
  } catch (e) { $("#figout").innerHTML = `<p class="note">figures unavailable: ${e.message}</p>`; }

  await wireSetup();
  try { await health(); } catch (e) { /* the page still works without it */ }

  let arms;
  try { arms = await api("/api/arms"); }
  catch (e) {
    // No dataset is the normal first launch of a downloaded copy, not a failure. Open Setup
    // and say the one thing that is true: you can start by adding an image.
    showSetup(true);
    $("#hdr").textContent = "no measurements yet";
    $("#armnote").textContent = "Add a mask or micrograph above to measure one, " +
      "or point the app at a SEM repo in Setup.";
    return;
  }
  $("#arm").innerHTML = arms.map((a) =>
    `<option value="${a.arm}">${a.arm} — ${a.n_frames} frames, ${a.n_cracks.toLocaleString()} cracks</option>`).join("");
  state.arm = arms[0].arm;
  // The arm dropdown already carries per-arm counts, so the header says the total once
  // instead of repeating every arm. Fewer words, same information.
  const tf = arms.reduce((n, a) => n + a.n_frames, 0);
  const tc = arms.reduce((n, a) => n + a.n_cracks, 0);
  $("#hdr").textContent = `${tf} frames · ${tc.toLocaleString()} cracks · ${arms.length} arms`;
  if (HEALTH && !HEALTH.sem_repo) showSetup(true);
  $("#arm").onchange = (e) => { state.arm = e.target.value; state.spec = ""; loadArm(); };
  $("#spec").onchange = (e) => { state.spec = e.target.value; loadArm(); };
  loadArm();
})();
