"use strict";
/* Charts are inline SVG built here rather than pulled from a CDN: this app is meant to run on
   a lab machine with no internet, and a chart that silently fails to render is worse than a
   table. Every chart also has a table beside it, which is also what the light-mode contrast
   WARN on two palette slots obliges. */

const $ = (s) => document.querySelector(s);
const state = { arm: null, spec: "", frames: [], frame: null, cracks: null, minArea: 0,
                sortKey: "frame", sortDir: 1 };
// Every row here is built with innerHTML, so anything from the record that lands inside an
// attribute has to be escaped. The definition strings are written in measure.py and contain
// apostrophes and parentheses today; one double quote added there later would otherwise end
// the attribute and swallow the rest of the row silently.
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (ch) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
const fmt = (v, d = 2) =>
  v === null || v === undefined ? "—"
  : typeof v === "number" ? (Number.isInteger(v) ? v.toLocaleString()
      : v.toLocaleString(undefined, { maximumFractionDigits: d })) : String(v);

async function api(path) {
  const r = await fetch(path);
  if (!r.ok) {
    // A bare "500" is not a message. FastAPI returns a JSON {detail} for its own
    // HTTPExceptions but a plain-text "Internal Server Error" body for an unhandled one,
    // so the only thing on screen for the case that most needs explaining was the number.
    let msg = `server error ${r.status}`;
    try {
      const d = await r.json();
      if (d && d.detail) msg = typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail);
    } catch (_) {
      if (r.status >= 500) msg = `server error ${r.status} — see the app's log for the cause`;
    }
    throw new Error(msg);
  }
  return r.json();
}

/* ---------------------------------------------------------------- frames table */
const FCOLS = [
  // THREE columns, because the frames table is now a 300 px list beside the detail pane
  // rather than a full-width card. It exists to pick a frame, not to be read: its job is
  // identity plus the one number you scan for. Everything else is one click away in Detail,
  // and all of it is in the CSV.
  ["frame", "Frame"],
  ["_cracks", "Cracks"],                       // "457 (+19 specks)"
  ["area_fraction", "Area"],
];

// The prefix every visible row shares, computed from what is actually on screen rather
// than from the specimen name: a filtered list can share more than the specimen, and an
// unfiltered one may share nothing at all.
let FRAME_PREFIX = "";

//: Which specimen groups the reader has opened. Kept across re-renders so a re-measure or
//: a sort does not collapse the group they are working in.
const GROUPS_OPEN = new Set();

function commonPrefix(names) {
  if (names.length < 2) return "";
  let p = names[0];
  for (const n of names) {
    let i = 0;
    while (i < p.length && i < n.length && p[i] === n[i]) i++;
    p = p.slice(0, i);
    if (!p) return "";
  }
  // Cut back to a separator so a truncated token is never shown, and keep at least a few
  // characters of identity in every row.
  const cut = Math.max(p.lastIndexOf("_"), p.lastIndexOf("-"));
  return cut > 0 ? p.slice(0, cut + 1) : "";
}

function shortFrame(name, prefix) {
  // The prefix is now the GROUP's, falling back to the arm's. Rows are grouped by
  // specimen and the group header already prints the specimen name, so inside a group
  // that part of every name is both redundant and the part that survives truncation:
  // all five frames of 260622_316_H_b2 rendered as the identical string
  // "260622_316_H_..." at 15ch, clipping exactly the discriminating tail
  // (back_CBS_01, front_CBS_01 ... front_CBS_04) -- and front vs back is a real
  // distinction in this corpus. 142 of 142 gated cells clipped; 139 were non-unique
  // within their own open group. Measured at 285 px of content in a 139 px cell.
  const pre = prefix || FRAME_PREFIX;
  return (pre && name.startsWith(pre) && name.length > pre.length + 2)
    ? name.slice(pre.length) : name;
}

function renderFrames() {
  const t = $("#frames");
  t.querySelector("thead").innerHTML = "<tr>" + FCOLS.map(([k, l]) =>
    `<th data-k="${k}">${k === "frame" && FRAME_PREFIX ? `…${l}` : l}` +
    `${state.sortKey === k ? (state.sortDir > 0 ? " ▲" : " ▼") : ""}</th>`
  ).join("") + "</tr>";
  // Composite cells, derived rather than stored, so the dataset keeps its raw fields.
  const derive = (f) => ({
    ...f,
    _cracks: f.n_cracks_measured,
    _p10min: (f.probe && f.probe.p10_min_per_mm) ?? null,
  });
  FRAME_PREFIX = commonPrefix(state.frames.map((f) => f.frame));
  const rows = [...state.frames].map(derive).sort((a, b) => {
    const x = a[state.sortKey], y = b[state.sortKey];
    if (x === y) return 0;
    if (x === null || x === undefined) return 1;
    if (y === null || y === undefined) return -1;
    return (x > y ? 1 : -1) * state.sortDir;
  });
  // GROUPED BY SPECIMEN, not one flat list of 142 rows. A specimen is the set of images
  // that belong together -- it is the unit every statistic in this app is computed over --
  // so a flat list asked the reader to do in their head the grouping the app was already
  // doing everywhere else. Collapsible, each header carrying its own count and median.
  const groups = new Map();
  for (const f of rows) {
    const k = f.specimen || "unparsed";
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(f);
  }
  const one = (f, groupPrefix) => {
    const noScale = f.scale_known ? "" : ` <span class="flag">no scale</span>`;
    return `<tr data-f="${esc(f.frame)}" aria-selected="${state.frame === f.frame}">` +
      FCOLS.map(([k]) => {
        // title= carries the WHOLE name, so the cell is still identifiable on hover and
        // to a screen reader even if the shortened form is itself clipped.
        if (k === "frame") return `<td class="ind" title="${esc(f[k])}">` +
          `${esc(shortFrame(f[k], groupPrefix))}${noScale}</td>`;
        if (k === "_cracks") {
          const sp = f.speck_count
            ? ` <span class="muted">+${f.speck_count.toLocaleString()}</span>` : "";
          return `<td>${fmt(f.n_cracks_measured)}${sp}</td>`;
        }
        return `<td>${fmt(f[k], 4)}</td>`;
      }).join("") + "</tr>";
  };
  t.querySelector("tbody").innerHTML = [...groups.entries()].map(([spec, fs]) => {
    // A group holding the selected frame is always open, so re-measuring or sorting never
    // hides the row the reader is working on.
    const open = GROUPS_OPEN.has(spec) || groups.size === 1 ||
                 fs.some((f) => f.frame === state.frame);
    const af = fs.map((f) => f.area_fraction).filter((v) => v != null).sort((x, y) => x - y);
    const med = af.length ? af[Math.floor(af.length / 2)] : null;
    const head = `<tr class="grp" data-grp="${esc(spec)}">` +
      `<td colspan="${FCOLS.length - 1}">${open ? "\u25be" : "\u25b8"} ${esc(spec)}` +
      ` <span class="u">${fs.length}</span></td>` +
      `<td class="u">${med == null ? "" : fmt(med, 4)}</td></tr>`;
    // The prefix every frame in THIS group shares, which the header above already names.
    const gp = commonPrefix(fs.map((f) => f.frame));
    return open ? head + fs.map((f) => one(f, gp)).join("") : head;
  }).join("");

  t.querySelectorAll("thead th").forEach((th) => th.onclick = () => {
    const k = th.dataset.k;
    state.sortDir = state.sortKey === k ? -state.sortDir : 1;
    state.sortKey = k; renderFrames();
  });
  t.querySelectorAll("tbody tr.grp").forEach((tr) => tr.onclick = () => {
    const k = tr.dataset.grp;
    if (GROUPS_OPEN.has(k)) GROUPS_OPEN.delete(k); else GROUPS_OPEN.add(k);
    renderFrames();
  });
  t.querySelectorAll("tbody tr:not(.grp)").forEach((tr) =>
    tr.onclick = () => selectFrame(tr.dataset.f));
}

/* ---------------------------------------------------------------- rose */
// A FULL ROSE, MIRRORED, WITH ITS NULL DRAWN ON IT.
//
// Three things were wrong with the half-disc this replaces, and only the first is cosmetic.
//
// 1. A crack has an AXIS, not a direction: 10° and 170° are nearly the same orientation.
//    The measurement already knows this (the resultant is computed on doubled angles), and
//    the convention in this literature -- FracPaQ, fractopo -- is to draw axial data as a
//    full bidirectional rose. Half a disc was the arithmetic showing through the chart.
// 2. THE NULL WAS COMPUTED AND NEVER SHOWN. rose_R_null is on every frame record and no
//    pixel of this chart used it, so a reader saw a lopsided rose and concluded
//    "preferentially oriented" every time -- which is exactly the failure the null exists
//    to prevent. A synthetic mask of straight lines at UNIFORM RANDOM angles returns
//    R = 0.267-0.285, at or above this corpus's median R of 0.257. The verdict now sits on
//    the chart, and when the rose does not beat its null the wedges are drawn muted.
// 3. There was no reference for the wedge lengths. The dashed ring is the EVEN SPLIT, 1/n
//    of the length in every bin, which is the right null for the quantity actually drawn.
//
// The ring and the verdict are deliberately different objects, because they are nulls for
// different statistics: the ring is the expected per-bin share, the verdict is the axial
// resultant against its permutation null. Drawing the resultant's threshold as a ring on
// the per-bin axis would be a number attached to the wrong object. The resultant appears as
// an ORIENTATION only -- a line through the centre at rose_theta_deg, no length claim --
// because an angle is the one thing this chart's angular axis can carry honestly.
function rose(hist, f) {
  const el = $("#rose");
  if (!hist || !hist.area_share) { el.innerHTML = `<p class="note">No orientation data.</p>`; return; }
  // cy leaves room above for the 0° label, which sat at y=6 and was clipped by the viewBox.
  const R = 104, cx = 150, cy = 132, share = hist.area_share, n = share.length;
  const max = Math.max(...share) || 1;
  const even = 1 / n;                      // uniform expectation for the drawn quantity
  const rAt = (v) => 10 + (R - 10) * (v / max);
  const beats = f && f.rose_beats_null === true;
  const known = f && f.rose_R != null && f.rose_R_null != null;
  // Muted when the rose does not beat chance: the shape is still worth seeing, it just is
  // not evidence, and colour is the only channel that says so before you read anything.
  const op = (v) => ((beats ? 0.34 : 0.14) + (beats ? 0.62 : 0.2) * v / max).toFixed(2);

  // Wedges, mirrored into the opposite half. 2px gap so adjacent fills never touch.
  let p = "";
  share.forEach((v, i) => {
    const r = rAt(v);
    [0, Math.PI].forEach((flip) => {
      const a0 = (i * 180 / n - 90) * Math.PI / 180 + 0.012 + flip;
      const a1 = ((i + 1) * 180 / n - 90) * Math.PI / 180 - 0.012 + flip;
      const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0);
      const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
      p += `<path d="M${cx},${cy} L${x0.toFixed(1)},${y0.toFixed(1)} A${r.toFixed(1)},${r.toFixed(1)} 0 0 1 ${x1.toFixed(1)},${y1.toFixed(1)} Z"
        fill="var(--s1)" fill-opacity="${op(v)}"
        stroke="var(--surface-2)" stroke-width="2"
        data-tip="${hist.bin_deg[i]}–${hist.bin_deg[i] + 15}°: ${(v * 100).toFixed(1)}% of length${
          v > even ? ` · above the ${(even * 100).toFixed(1)}% even split` : ""}"></path>`;
    });
  });

  // The even-split ring. Labelled "even", NOT as a significance threshold: with a finite
  // number of segments the bins scatter around it, so one bin crossing it means nothing on
  // its own. The verdict below is the test.
  const ringR = rAt(even);
  const ring = `<circle cx="${cx}" cy="${cy}" r="${ringR.toFixed(1)}" fill="none"
      stroke="var(--text-muted)" stroke-width="1" stroke-dasharray="3 3" opacity="0.8"
      data-tip="Even split: ${(even * 100).toFixed(1)}% of length in every bin, which is what uniform orientation would give"></circle>
    <text x="${cx}" y="${(cy - ringR - 3).toFixed(0)}" fill="var(--text-muted)" font-size="9.5"
      text-anchor="middle">even</text>`;

  // Labelled at BOTH ends of each axis. Not a duplicate: for axial data 0° and the point
  // opposite it are the same orientation, so both ends genuinely carry that label -- and a
  // full circle labelled on one side only reads as a chart that did not finish drawing.
  // 0° is vertical in the image, 90° horizontal, matching the angle the measurement reports.
  let ticks = "";
  [0, 45, 90, 135].forEach((d) => {
    const a = (d - 90) * Math.PI / 180;
    [0, Math.PI].forEach((flip) => {
      ticks += `<text x="${(cx + (R + 14) * Math.cos(a + flip)).toFixed(0)}" y="${(cy + (R + 14) * Math.sin(a + flip)).toFixed(0)}"
        fill="var(--text-muted)" font-size="9.5" text-anchor="middle" dominant-baseline="middle">${d}°</text>`;
    });
  });

  // The resultant ORIENTATION, drawn only when it beats its null. An angle on an angular
  // axis is honest; its magnitude is not on this chart's scale, so it stays in the caption.
  let axis = "";
  if (beats && f.rose_theta_deg != null) {
    const a = (f.rose_theta_deg - 90) * Math.PI / 180;
    axis = `<line x1="${(cx - (R + 6) * Math.cos(a)).toFixed(1)}" y1="${(cy - (R + 6) * Math.sin(a)).toFixed(1)}"
      x2="${(cx + (R + 6) * Math.cos(a)).toFixed(1)}" y2="${(cy + (R + 6) * Math.sin(a)).toFixed(1)}"
      stroke="var(--s2)" stroke-width="2" stroke-linecap="round"
      data-tip="Mean orientation ${f.rose_theta_deg}°, the axial resultant direction"></line>`;
  }

  // Direct-label the dominant bin only: selective labels, never one per wedge.
  const top = share.indexOf(max);
  const ta = ((top + 0.5) * 180 / n - 90) * Math.PI / 180;
  const tl = `<text x="${(cx + (R * 0.58) * Math.cos(ta)).toFixed(0)}" y="${(cy + (R * 0.58) * Math.sin(ta)).toFixed(0)}"
    fill="var(--text-primary)" font-size="12" font-weight="600" text-anchor="middle"
    dominant-baseline="middle">${(max * 100).toFixed(0)}%</text>`;

  // The verdict, on the chart. Identity is never colour alone: the word is here too.
  const verdict = !known ? "" : `<g>
    <text x="${cx}" y="${cy + R + 34}" text-anchor="middle" font-size="11.5" font-weight="600"
      fill="${beats ? "var(--text-primary)" : "var(--text-muted)"}">${
        beats ? `Oriented near ${f.rose_theta_deg}°` : "Not distinguishable from random"}</text>
    <text x="${cx}" y="${cy + R + 48}" text-anchor="middle" font-size="10" fill="var(--text-muted)"
      data-tip="${esc(f.rose_null || "")}">R = ${f.rose_R} · chance reaches ${f.rose_R_null}</text></g>`;

  const note = document.querySelector("#rosenote");
  if (note) {
    // Read the weighting off the payload rather than hardcoding it. The caption said
    // "Area-weighted" for a while after the rose became length-weighted, because the word
    // lived in the HTML and the behaviour lived in Python.
    note.textContent = `${hist.weighted_by === "segment length" ? "Length" : hist.weighted_by}`
      + `-weighted, 15° bins, mirrored — a crack has an axis, not a direction.`;
  }
  el.innerHTML = `<svg viewBox="0 0 300 ${cy + R + 56}" width="100%" role="img"
    aria-label="${hist.weighted_by}-weighted crack orientation by skeleton branch, 15 degree bins, mirrored about the centre. ${
      known ? (beats ? `Oriented near ${f.rose_theta_deg} degrees; resultant ${f.rose_R} against a chance level of ${f.rose_R_null}.`
                     : `Not distinguishable from random: resultant ${f.rose_R} against a chance level of ${f.rose_R_null}.`) : ""}">
    ${ring}${p}${axis}${ticks}${tl}${verdict}</svg>`;
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
// "Length px" was SkeletonLength_px alone -- the region's whole network centreline, under
// a name that reads as the crack's length. Both columns, both named: the longest single
// crack tip to tip, and the network total the region's branches add up to.
const CCOLS = [["crack_id", "ID"], ["area_px", "Area px"],
  ["TipToTipGeodesic_px", "Longest px"], ["SkeletonLength_px", "Network px"],
  ["MeanWidth_px", "Mean W"], ["length_is_censored", "Censored"], ["area_um2", "Area µm²"]];

async function selectFrame(name) {
  state.frame = name;
  const f = state.frames.find((x) => x.frame === name);
  renderFrames();
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
    //
    // TWO ROWS, because they are two quantities. This row used to carry
    // max(SkeletonLength_px) -- the total centreline of the largest NETWORK, every branch
    // added up -- under the name "Longest crack", which is what a reader compares with a
    // Varestraint MCL. It read 1578 µm on a frame 213 µm across. The row below it is that
    // network number, kept and named for what it is.
    ...(f.mcl_um ? [[`<span title="${esc(f.mcl_definition || "")}">Longest crack (MCL)</span>`,
      // The bracket note is written beside the number in measure.py and belongs on the
      // bracket, not in the CSV alone: the two ends are a bracket only if the reader is
      // told which way each one is biased.
      (f.mcl_um_uncensored_only != null && f.mcl_censored
        ? `${fmt(f.mcl_um, 1)} µm <span class="muted" title="${esc(f.mcl_bracket_note || "")}">censored — ${fmt(f.mcl_um_uncensored_only, 1)} µm if edge-touching cracks are dropped</span>`
        : `${fmt(f.mcl_um, 1)} µm <span class="muted">${f.mcl_censored === false ? "does not touch an edge" : ""}</span>`) +
      `<span class="muted"><br>tip to tip along one crack` +
      `${f.mcl_share_of_its_network != null ? `, ${(100 * f.mcl_share_of_its_network).toFixed(0)}% of its own network's centreline` : ""}` +
      `${f.mcl_has_cycles ? " · that region loops, so this is the shorter way round" : ""}` +
      `${f.mcl_method === "sampled_sources_lower_bound" ? " · too large to sweep exhaustively, so a lower bound" : ""}` +
      `${f.n_regions_geodesic_sampled ? ` · ${f.n_regions_geodesic_sampled} region(s) sampled rather than swept` : ""}` +
      `${f.n_regions_geodesic_undefined ? ` · ${f.n_regions_geodesic_undefined} closed-loop region(s) have no tip and are not in this max` : ""}</span>`]] : []),
    ...(f.largest_network_centreline_um ? [[`<span title="${esc(f.largest_network_centreline_definition || "")}">Largest network centreline</span>`,
      // SAME PRECISION as the MCL row above it. These two are printed next to each other
      // for the reader to compare, and on an unbranched region they are the same number --
      // at 0 dp against the other row's 1 dp that identity rendered as "30.9" beside "31",
      // which reads as a discrepancy in exactly the case where there is none.
      `${fmt(f.largest_network_centreline_um, 1)} µm <span class="muted">` +
      `${f.largest_network_centreline_um_uncensored_only != null && f.largest_network_centreline_censored
          ? `<span title="${esc(f.mcl_bracket_note || "")}">censored — ${fmt(f.largest_network_centreline_um_uncensored_only, 1)} µm if edge-touching regions are dropped</span><br>` : ""}` +
      `every branch of one connected network added together — a network size, not a crack length</span>`]] : []),
    ...(f.tcl_um ? [["Total length (TCL)", fmt(f.tcl_um, 0) + " µm"]] : []),
    ["Junctions", `${fmt(f.n_junctions)} <span class="muted">${fmt(f.n_triple)} triple, ${fmt(f.n_quadruple_plus)} quad+</span>`],
    // Weighted by LENGTH, because this caveat sits beside MCL and TCL. The count share
    // was the only one reported and it understates by ~5x in SEM and ~3x in TXM: a frame
    // can be 6% of regions censored and 44% of crack AREA censored.
    ["Touching frame edge", f.censored_share === null ? "—"
      : `${((f.censored_share_by_length ?? f.censored_share) * 100).toFixed(0)}% <span class="muted">of crack length` +
        `${f.censored_share_by_area != null ? `, ${(f.censored_share_by_area * 100).toFixed(0)}% of area` : ""}` +
        `, ${(f.censored_share * 100).toFixed(1)}% of regions</span>`],
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

  { const pin = $("#crackpin"); if (pin) pin.hidden = true; }
  $("#mask").hidden = false;
  $("#mask").src = `/api/mask/${state.arm}/${encodeURIComponent(name)}`;
  $("#mask").alt = `Crack mask for ${name}`;
  $("#masknote").textContent = `${state.arm} — black is crack.`;

  rose(f.orientation_hist_deg, f);
  renderSpecimens();      // the strip follows the frame's specimen
  renderReadout();
  // The Mark pane is rendered once when the tab is shown, which happens BEFORE the first
  // frame is auto-selected -- so opening the app on a loaded corpus showed "Add an image
  // to mark" with 142 frames in the list beside it. Re-render it when the frame changes.
  if (TAB === "mark") { ED.frame = null; renderMark(); }
  try {
    const d = await api(`/api/cracks?frame=${encodeURIComponent(name)}&arm=${encodeURIComponent(state.arm)}`);
    state.cracks = d;
    renderCracks();
  } catch (e) { $("#cracknote").textContent = "Could not load cracks: " + e.message; }
}

//: The largest N regions by area. This was the biggest text mass on the page -- 305 rows
//: and 1,547 words, more than every label and caption in the app combined -- and it is the
//: least likely thing a researcher needs first. Ranking by area puts the informative rows
//: at the top: this project has already seen one region hold 97.45% of total area while
//: 305 components read as fragmentation. The rest is in the CSV, which now exports what the
//: screen is filtering.
const CRACK_ROWS = 25;

// The pin is positioned as a FRACTION of the image, not in pixels: the mask is displayed
// scaled to fit and the centroid is in the image's own coordinates, so anything else
// drifts as the window changes.
function pinCrack(c) {
  const img = $("#mask"), pin = $("#crackpin");
  const f = state.frames.find((x) => x.frame === state.frame);
  if (!img || pin === null || !f || !f.width_px || c.centroid_x_px == null) return;
  pin.hidden = false;
  pin.style.left = (100 * c.centroid_x_px / f.width_px) + "%";
  pin.style.top = (100 * c.centroid_y_px / f.height_px) + "%";
  pin.title = `region ${c.crack_id}: ${fmt(c.area_px)} px`;
  img.scrollIntoView({ behavior: "smooth", block: "nearest" });
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
  const shown = rows.slice(0, CRACK_ROWS);
  t.querySelector("tbody").innerHTML = shown.map((c) => "<tr>" +
    CCOLS.map(([k]) => `<td>${typeof c[k] === "boolean" ? (c[k] ? "yes" : "") : fmt(c[k], 3)}</td>`).join("") +
    "</tr>").join("") +
    (rows.length > shown.length
      ? `<tr><td colspan="${CCOLS.length}" class="u">showing the largest ${shown.length}` +
        ` of ${rows.length.toLocaleString()} — the rest is in the CSV</td></tr>`
      : "");
  // The size distribution is built on ALL the rows, not the 25 displayed: it is a
  // distribution, and truncating its input would change its shape.
  // A CRACK ROW POINTS AT A PLACE ON THE IMAGE. centroid_x_px and centroid_y_px are
  // measured and served on every row and were referenced nowhere, so a researcher could
  // read that region 7 holds 55% of the crack area and had no way to find region 7. This
  // is the only way to sanity-check a mask by eye, and ImageJ's ROI Manager has had it
  // since 2008.
  t.querySelectorAll("tbody tr").forEach((tr, i) => {
    tr.onclick = () => {
      const c = shown[i];
      if (!c) return;
      t.querySelectorAll("tbody tr").forEach((x) => x.removeAttribute("aria-selected"));
      tr.setAttribute("aria-selected", "true");
      pinCrack(c);
    };
  });
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
  const note = $("#listcount");
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

// A normal-theory interval on a small non-negative quantity can reach below zero. Printing
// the clamp as "0.00%" asserts a measured lower bound of exactly zero, which the data does
// not support — it is the method running out of validity. Five specimen-arms hit this.
function ciLo(ci) {
  if (!ci) return "—";
  if (!ci.ci95_lo_clamped) return pct(ci.ci95_lo);
  return `<span class="flag" title="${ci.ci95_lo_note || ""}">&lt;0</span>`;
}

// THE ADVICE DEPENDS ON THE SPECIMEN, so the tooltip cannot be a constant. The same
// static string was attached to every badge, including the specimens where this app's own
// stage.py concludes that more tiles in the same patch will NOT narrow the interval
// because the fields are tracking a spatial gradient. The read-out already suppresses that
// clause for those specimens; the badge went on asserting it, so the app gave a materials
// researcher the wrong instruction in the one place it was most likely to be read.
function raBadge(ci, rec) {
  if (!ci || ci.pct_relative_accuracy == null) return "";
  const v = ci.pct_relative_accuracy;
  const grad = rec && rec.stage_gradient && rec.stage_gradient.significant;
  const tip = "ASTM E562 relative accuracy: the 95% interval as a percentage of the mean. "
    + "The usual target is 10% or better. " + (grad
      ? "These fields trend across one patch, so more tiles in the SAME patch will not "
        + "narrow it — more patches would."
      : "Above it, more fields narrow the interval on this site — they do not make it "
        + "comparable to another specimen.");
  return `<span class="ra${v > 10 ? " bad" : ""}" title="${esc(tip)}">±${v}%</span>`;
}

// THE MAGNIFICATION SPAN, because the card otherwise shows two field counts and no reason.
// Four specimen-arms hold nine fields at 51.883 nm/px plus one overview at 337.2396, and
// the interval is computed over the nine (see analysis/specimen_stats.py). Without this
// row the header reads "10 fields" and the interval beside it reads "9 fields", which
// looks like a bug rather than the rule it is. Rendered on single-magnification specimens
// too: "all N fields at one scale" is part of what the interval claims.
function magRow(r) {
  const g = r.magnification_groups || [];
  if (!g.length || g[0].nm_per_px == null) return null;
  const det = g[0], off = g.slice(1);
  const one = (x) => `${x.nm_per_px} <span class="u">nm/px · ${x.n_fields} field${x.n_fields === 1 ? "" : "s"} · resolves ${x.min_resolvable_width_um} µm</span>`;
  if (!off.length) {
    return ["Magnification", `${one(det)} <span class="u">· one scale</span>`];
  }
  // The tooltip used to end "and still counted in the area analysed". That stopped being
  // true when the additive totals moved onto the determination, and a caveat that
  // describes the previous behaviour is worse than none.
  const tip = "ASTM E562 fixes the magnification before the fields are counted: a coarser "
    + "pixel is a coarser minimum resolvable width, so these estimate different "
    + "populations and their mean is not a measurement of either. The excluded fields are "
    + "still measured individually, on their own cards; they are left out of every total "
    + "and every median on THIS card.";
  // AND SAY HOW MUCH WAS LEFT OUT. It was computed, stored and rendered nowhere. On
  // MAR_AmbB_HIP the excluded 0.716 mm² is LARGER than the 0.610 mm² that remains, which
  // is the 10.6x field-of-view point made concrete and the most persuasive single number
  // for why the overview was never a replicate of the nine. "Not added" is said out loud
  // because two areas side by side otherwise invite exactly the sum this rule forbids.
  const nOff = off.reduce((n, x) => n + x.n_fields, 0);
  const off_area = r.area_off_determination_mm2 == null ? "" :
    `<br><span class="u">${num(r.area_off_determination_mm2, 3)} mm² of material sits in `
    + `${nOff === 1 ? "that field" : `those ${nOff} fields`} and is not added to the `
    + `${num(r.area_analysed_mm2, 3)} mm² above</span>`;
  return ["Magnification",
    `${one(det)}<br><span class="flag" title="${esc(tip)}">not in the interval:</span> `
    + off.map((x) => `${one(x)}, mean ${pct(x.area_fraction_mean)}`).join(" · ") + off_area];
}

function specimenCard(r) {
  const ci = r.area_fraction_ci;
  const scaled = r.scale_known_frames > 0;
  const off = scaled ? "" : ' class="off"';
  const ds = r.detector_sensitivity, as = r.arm_sensitivity;
  const dets = Object.entries(r.detectors || {}).map(([k, v]) => `${k} ${v}`).join(" · ");
  const rows = [
    ["Crack area fraction",
     ci ? `<span class="big">${pct(ci.mean)}</span> <span class="ci">95% CI ${ciLo(ci)}–${pct(ci.ci95_hi)}, ${ci.n_fields} field${ci.n_fields === 1 ? "" : "s"}${ci.n_fields_off_determination ? ` at ${ci.nm_per_px} nm/px` : ""}</span>${raBadge(ci, r)}`
        : `<span class="big">${pct(r.area_fraction_median)}</span> <span class="ci">${r.no_ci_reason && r.no_ci_reason.indexOf("split across magnifications") >= 0 ? `median of ${r.n_fields} fields — no single magnification has three` : `median of ${r.n_fields} field${r.n_fields > 1 ? "s" : ""} — under 3, no interval`}</span>`],
    ["P10", `${num(r.p10_min_per_mm)} <span class="u">/mm min</span> · ${num(r.p10_mean_per_mm)} <span class="u">/mm mean</span>`],
    ["P21 · P20", `${num(r.p21_skeleton_mm_per_mm2)} <span class="u">mm/mm²</span> · ${num(r.p20_per_mm2, 0)} <span class="u">/mm²</span>`],
    // null / 1000 is 0 in JavaScript, so an unscaled specimen was reporting "0.00 mm" of
    // total crack length -- a measured zero where the truth is "not measurable".
    // MCL here is the longest tip-to-tip crack, not the largest network's total
    // centreline; the two are separate columns since they stopped being the same number.
    ["MCL · TCL", `${num(r.mcl_um)} <span class="u">µm</span> · ${num(r.tcl_um_total == null ? null : r.tcl_um_total / 1000, 2)} <span class="u">mm</span>`],
    ["Largest network", `${num(r.largest_network_centreline_um)} <span class="u">µm centreline</span>`],
  ];
  const mag = magRow(r);
  if (mag) rows.push(mag);
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

//: Set by renderReadout, rendered by renderSpecimens. Held rather than re-fetched because
//: both are driven by loadArm and the order between them is not guaranteed.
let ARM_STATEMENTS = [];
//: The statements under the current figure, so the drawer can open their basis.
let FIG_SAID = [];

function armStatements() {
  if (!ARM_STATEMENTS.length) return "";
  // FINDINGS OUT, LIMITS IN. Seven statements of which two are results and five are
  // caveats reads as five caveats: the useful part is outnumbered on its own line. The
  // established findings stay open; the limits collapse to one summary the reader opens
  // when they want to know what the findings do not cover. Not hidden -- one click, and
  // the count is on the line, so a reader can see there are five without reading five.
  const line = (st, i) =>
    `<div class="ro-line ${st.level}" data-ro="arm:${i}" tabindex="0" role="button">
       <span class="mk">${MARK[st.level] || "\u00b7"}</span>
       <span class="tx">${esc(st.text)}</span>
     </div>`;
  const findings = ARM_STATEMENTS.map((st, i) => [st, i]).filter(([st]) => st.level === "good");
  const limits = ARM_STATEMENTS.map((st, i) => [st, i]).filter(([st]) => st.level !== "good");
  let html = "";
  if (findings.length) {
    html += `<h3 class="sect">What this arm establishes</h3>`
      + `<div class="ro armro">` + findings.map(([st, i]) => line(st, i)).join("") + `</div>`;
  }
  if (limits.length) {
    html += `<details class="limits"><summary>${limits.length} limit${
      limits.length === 1 ? "" : "s"} on these numbers</summary>`
      + `<div class="ro armro">` + limits.map(([st, i]) => line(st, i)).join("") + `</div></details>`;
  }
  return html;
}

function wireArmStatements() {
  // Same interaction as every other read-out line: click opens the basis and the hedge in
  // the definitions drawer, so the explanation is addressable instead of a hover tooltip.
  document.querySelectorAll('#armro [data-ro]').forEach((el) => {
    const open = () => openDefs(ARM_STATEMENTS[+el.dataset.ro.split(":")[1]]);
    el.onclick = open;
    el.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } };
  });
}

async function renderSpecimens() {
  let rows;
  try { rows = await api(`/api/specimens?arm=${encodeURIComponent(state.arm)}`); }
  catch (e) {
    $("#specnote").innerHTML = `<span class="flag">${e.message}</span>`;
    renderStrip(null);
    return;
  }
  const one = state.spec ? rows.find((r) => r.specimen === state.spec) : null;
  // The strip shows the selected specimen, or the one the selected frame belongs to, so the
  // headline number is never blank and never has to be scrolled to.
  const f = state.frames.find((x) => x.frame === state.frame);
  renderStrip(one || (f ? rows.find((r) => r.specimen === f.specimen) : null));
  if (one) {
    $("#specwrap").hidden = false;
    const ci0 = one.area_fraction_ci;
    $("#specnote").textContent = `${one.specimen} · `
      + `${ci0 ? pct(ci0.mean) : pct(one.area_fraction_median)} crack area · `
      + `${one.n_fields} fields`;
    $("#specbody").innerHTML = specimenCard(one);
  } else {
    const withCI = rows.filter((r) => r.area_fraction_ci);
    const meeting = withCI.filter((r) => r.area_fraction_ci.pct_relative_accuracy <= 10);
    // The E562 count used to live here as a bare clause. It is the first arm-level
    // conclusion now, with its basis and its hedge, so this is just the count.
    // NO TABLE OF ALL SPECIMENS. It listed fourteen rows by seven columns and ranked
    // nothing -- it could not, since one imaged site per specimen makes the ordering it
    // implied unestimable -- and every number in it is on that specimen's own card. What
    // it was actually for is above, as arm-level conclusions.
    $("#specwrap").hidden = true;
    $("#specnote").textContent = "";
    $("#specbody").innerHTML = "";
  }
}

// ---------------------------------------------------------------------------------------
// TABS. The selector is the navigation, so there is no nav furniture: the frame list stays
// on the left and this changes what you are looking at. Read-out is the default because the
// owner's request was "tell me what it says", not "give me another table".
// SIX, NOT EIGHT. "Frame detail", "Orientation" and "Cracks" were three destinations for
// one question -- everything else about the frame you have selected -- so they are one
// scrolling pane. A tab strip is navigation only while a reader can hold it in their head.
// FOUR TABS, MARK FIRST. Read-out, Mask and Details were three destinations all
// answering "what about this frame?", so seeing one frame meant visiting three places.
// They are one Analysis page now. And the order follows the work: mark a mask, then ask
// what it measures, then compare, then export.
// THREE TABS. Compare is gone: its table ranked nothing (it could not -- one imaged site
// per specimen), its per-row numbers are each on their own specimen's card, and what it
// was actually for -- what the whole arm supports -- is five sentences that belong with
// the other conclusions. A tab whose content is "the same numbers again, in a grid" is
// navigation cost with no answer at the end of it.
const TABS = [
  ["mark", "Mark"],
  ["analysis", "Analysis"],
  ["figure", "Figure"],
];
let TAB = "mark";

//: Tabs that are about the NUMBERS. The statistics strip belongs to these and not to
//: Mark: drawing needs to know which image is open, not what its 95% CI is.
const ANALYSIS_TABS = new Set(["analysis", "figure"]);

function showTab(id) {
  TAB = id;
  TABS.forEach(([k]) => { $("#pane-" + k).hidden = k !== id; });
  // THE DRAWING PAGE IS A DRAWING PAGE. Opening the editor used to put two bars naming
  // the same image above the canvas -- the picker in the header, and the statistics strip
  // ("9.65% crack area, 95% CI 6.68%-12.61%, +/-31%: wider than E562's precision target")
  // -- which is 160 px of numbers you cannot act on while holding a brush, and the second
  // of two answers to "which image is this". The strip is an assertion about the data
  // currently loaded, so it must never be behind a click ON THE PAGES THAT READ DATA; on
  // the page where you CHANGE the data it is noise, and it is stale the moment you paint.
  // It comes back, with the new numbers, the moment you switch to Analysis.
  $("#strip").hidden = !ANALYSIS_TABS.has(id);
  // Same reasoning for the two header buttons that only make sense once there ARE numbers.
  // The drawing page keeps what drawing needs -- the image picker, + Add image -- and
  // Setup, because a first-run user has to be able to reach it. Definitions and CSV come
  // back on the analysis tabs, where the numbers they describe are on screen.
  $("#defsbtn").hidden = !ANALYSIS_TABS.has(id);
  $("#csv").hidden = !ANALYSIS_TABS.has(id);
  if (!ANALYSIS_TABS.has(id)) $("#defs").hidden = true;   // and close the drawer
  // Repaint the strip: whether it mirrors the top conclusion depends on which tab this is
  // (it does not, on Analysis, where the read-out already shows it), so leaving the strip
  // alone across a tab switch would strand the previous tab's version of it.
  if (typeof STRIP_REC !== "undefined" && STRIP_REC) renderStrip(STRIP_REC);
  $("#tabs").querySelectorAll("button").forEach((b) =>
    b.setAttribute("aria-selected", String(b.dataset.tab === id)));
  // The figure is expensive and the rose needs a laid-out box, so both render on reveal
  // rather than on every frame change.
  if (id === "figure" && typeof window.figRenderRef === "function") window.figRenderRef();
  if (id === "mark") renderMark();
  if (id === "analysis") {
    const rf = state.frames.find((x) => x.frame === state.frame) || {};
    rose(rf.orientation_hist_deg, rf);
  }
}

function wireTabs() {
  $("#tabs").innerHTML = TABS.map(([k, label]) =>
    `<button role="tab" data-tab="${k}" aria-selected="${k === TAB}">${label}</button>`).join("");
  $("#tabs").querySelectorAll("button").forEach((b) => {
    b.onclick = () => showTab(b.dataset.tab);
  });
  showTab(TAB);
}

// ---------------------------------------------------------------------------------------
// THE STRIP. The headline number and its caveats, never scrolling away. On the old page it
// scrolled off at the first flick, and its caveats were in hover text — but they are
// assertions about the data currently loaded, not stable definitions, so they must not be
// behind any click at all.
let STRIP_REC = null;

function renderStrip(rec) {
  STRIP_REC = rec;
  const el = $("#strip");
  if (!rec) { el.innerHTML = `<span class="who">Select a specimen.</span>`; return; }
  const ci = rec.area_fraction_ci;
  const ds = rec.detector_sensitivity;
  const a = rec.arm_sensitivity;
  const bits = [
    `<span class="who">${rec.specimen}</span>`,
    ci ? `<span class="big">${pct(ci.mean)}</span>` : `<span class="big">${pct(rec.area_fraction_median)}</span>`,
    `<span class="u">crack area</span>`,
    // THE BADGE IS SUPPRESSED WHEN THE READ-OUT LINE BELOW ALREADY CARRIES THE SAME
    // NUMBER. Both render on this one line, 70 px apart, and at different roundings: the
    // badge prints pct_relative_accuracy raw (±30.7%) and the statement prints it at
    // :.0f (±31%). One quantity shown twice at two values reads as two quantities, which
    // is a poor trade in an app whose pitch is that its numbers are careful. The badge
    // loses rather than the sentence: the sentence says what the number MEANS and carries
    // the E562 target beside it, and its tooltip keeps the per-specimen remedy.
    ci ? `<span class="ci">95% CI ${ciLo(ci)}–${pct(ci.ci95_hi)}</span>${
           /precision target/.test(RO_TOP.text || "") ? "" : raBadge(ci, rec)}`
       : `<span class="ci">no interval, ${rec.n_fields} field${rec.n_fields === 1 ? "" : "s"}</span>`,
    `<span class="u">${rec.n_fields} fields${rec.n_frames !== rec.n_fields ? ` / ${rec.n_frames} frames` : ""}</span>`,
  ];
  // The strip prints the specimen's field count next to an interval computed over fewer
  // of them. Unexplained, that is the app contradicting itself in its own headline.
  // ...and only when there IS one. Gated on n_fields_off_determination alone, the banner
  // read "interval over 3 of 4 fields · one magnification" beside "no interval, 4 fields"
  // on the same line of the uploads strip, where area_fraction_ci is null by design. The
  // strip is the one element that must never be behind a click because it carries
  // assertions about the data currently loaded; here it contradicted itself in a single
  // line, and the false half was the half that sounded authoritative.
  if (ci && rec.n_fields_off_determination) {
    const g = (rec.magnification_groups || [])[0] || {};
    bits.push(`<span class="banner" title="${esc((ci && ci.magnification_note) || "")} ASTM E562 fixes the magnification before the fields are counted, and this repo's own rule is that pooling frames of unequal physical area is the error the standards exist to prevent.">interval over ${g.n_fields} of ${rec.n_fields} fields · one magnification</span>`);
  }
  if (ds && Math.abs(ds.cbs_over_etd_median - 1) > 0.2) {
    bits.push(`<span class="banner bad" title="CBS against ETD on ${ds.n_fields_both_detectors} fields imaged both ways. Detector is confounded with specimen here.">detector ×${ds.cbs_over_etd_median}</span>`);
  }
  if (a && !a.n_frames_corrected) {
    bits.push(`<span class="banner" title="The gated and machine arms are identical on all ${a.n_paired_frames} frames of this specimen.">no human review</span>`);
  }
  // THE TOP CONCLUSION, IN THE STRIP. Making Mark the default tab put the read-out behind
  // a click, and the first thing asked afterwards was where the conclusions had gone. The
  // most severe statement now sits with the headline number, always visible, and says how
  // many more there are.
  // NOT ON ANALYSIS, where the full read-out is already on screen and this line is its
  // first card -- the same sentence twice, 200 px apart, on the densest tab in the app.
  // The mirror exists because making Mark the default put the conclusions behind a click;
  // it earns its place on Mark, Compare and Figure, and nowhere else.
  if (RO_TOP.text && TAB !== "analysis") {
    bits.push(`<span class="banner ${RO_TOP.level === "bad" ? "bad" : ""}" ` +
      `id="striptop" title="${esc(RO_TOP.basis || "")}">${MARK[RO_TOP.level] || ""} ` +
      `${esc(RO_TOP.text)}${RO_TOP.more ? ` <span class="u">+${RO_TOP.more}</span>` : ""}</span>`);
  }
  if (rec.scale_known_frames === 0) {
    bits.push(`<span class="banner" title="No frame in this specimen has a recoverable nm/px, and the corpus spans a 249x magnification range, so there is no defensible default.">no scale</span>`);
  }
  el.innerHTML = bits.join(" ");
}

// ---------------------------------------------------------------------------------------
// THE READ-OUT. Four or five sentences instead of a table. Each line is clickable and
// opens its own reasoning in the definitions drawer, so the "why" is one click from the
// number rather than on hover — 2,392 words used to live in 398 title= attributes, which
// is unreachable on touch and undiscoverable on a laptop.
const MARK = { good: "●", warn: "▲", bad: "✕", info: "·" };

// ONE LIST, SEVERITY FIRST, CAPPED. Two sections of four each showed eight statements and
// collapsed nothing, because the cap was per section while the reader sees the total. The
// specimen/frame distinction still matters, so it becomes a tag on the line rather than a
// heading over a group -- which also removes two headings' worth of words.
//
// Sorted so a reader can stop after the first line and not have missed the worst thing.
const SEV = { bad: 0, warn: 1, good: 2, info: 3 };
const RO_SHOWN = 5;

function roRender(groups) {
  const all = [];
  for (const [heading, sts] of Object.entries(groups)) {
    (sts || []).forEach((st, i) => all.push({ st, key: `${heading}:${i}`, heading }));
  }
  if (!all.length) return "";
  all.sort((a, b) => (SEV[a.st.level] ?? 9) - (SEV[b.st.level] ?? 9));
  const one = (x, hidden) =>
    `<div class="ro-line ${x.st.level}" data-ro="${x.key}" tabindex="0" role="button"${hidden ? " hidden" : ""}>
       <span class="mk">${MARK[x.st.level] || "\u00b7"}</span>
       <span class="tx">${x.st.text}</span>
       <span class="who">${x.heading}</span>
     </div>`;
  const rest = all.slice(RO_SHOWN);
  return all.slice(0, RO_SHOWN).map((x) => one(x, false)).join("") +
    (rest.length
      ? rest.map((x) => one(x, true)).join("") +
        `<button class="ro-more">${rest.length} more</button>`
      : "");
}

let RO = {};

//: The single most severe statement, mirrored into the strip so a conclusion is never
//: behind a tab. Set by renderReadout, read by renderStrip.
let RO_TOP = {};

async function renderReadout() {
  const el = $("#readout");
  const f = state.frames.find((x) => x.frame === state.frame);
  const q = new URLSearchParams({ arm: state.arm });
  if (state.frame) q.set("frame", state.frame);
  if (state.spec) q.set("specimen", state.spec);
  let d;
  try { d = await api(`/api/readout?${q}`); }
  catch (e) { el.innerHTML = `<p class="ro-empty">${e.message}</p>`; return; }
  RO = { specimen: d.specimen || [], frame: d.frame || [] };
  // The arm statements are kept OUT of roRender: they belong to Compare, where the table
  // they describe is, and repeating them in the Analysis list would be the same sentence
  // in two panes again. They still go into RO so the definitions drawer can open them --
  // the key matches the data-ro prefix armStatements() emits.
  ARM_STATEMENTS = d.arm_statements || [];
  RO.arm = ARM_STATEMENTS;
  const armEl = $("#armro");
  if (armEl) { armEl.innerHTML = armStatements(); wireArmStatements(); }

  const body = roRender({ specimen: RO.specimen, frame: RO.frame });
  // Severity order is the same rule the list uses, so the strip and the list agree about
  // which statement matters most.
  const all = [...(RO.specimen || []), ...(RO.frame || [])]
    .sort((a, b) => (SEV[a.level] ?? 9) - (SEV[b.level] ?? 9));
  RO_TOP = all.length
    ? { text: all[0].text, level: all[0].level, basis: all[0].basis, more: all.length - 1 }
    : {};
  // THE QUESTION AND ITS ANSWER ARE ON SCREEN; the working is one click away.
  //
  // These were collapsed behind a single summary line reading "Not determinable here:
  // crack mode · path roughness · ...", on the grounds that they were 51 words restating
  // questions the reader may not have asked. That was wrong about which reader. The
  // owner asked thrice for a transgranular/intergranular call -- most recently proposing
  // linearity as the discriminator, which is the exact proxy the crack-mode entry
  // refutes with measurements. The app HAD considered the question, HAD reached a
  // conclusion, and had put it where nobody would find it. "This cannot be determined
  // from this data, here is why, and here is the one experiment that would settle it" IS
  // a conclusion, and for a researcher deciding what to image next it is the most
  // actionable one here.
  //
  // So each question and its answer are visible, and only the why and the would-need are
  // behind the disclosure. That is 4 questions and 4 answers, not 51 words of prose.
  const refusals = (d.refusals || []).length ? `
    <h3 class="sect">Asked and answered: not from this data</h3>
    <div class="refuse-all-open">
      ${(d.refusals || []).map((r) => `
        <div class="refuse">
          <h4>${esc(r.question)}</h4>
          <div class="ans">${esc(r.answer)}</div>
          <details><summary>Why, and what would answer it</summary>
            <p>${r.why}</p>
            ${r.would_need && r.would_need.length
              ? `<ul>${r.would_need.map((x) => `<li>${x}</li>`).join("")}</ul>` : ""}
            ${r.not_this ? `<p><strong>Not this:</strong> ${r.not_this}</p>` : ""}
          </details>
        </div>`).join("")}
    </div>` : "";

  el.innerHTML = (body || `<p class="ro-empty">Nothing this data supports saying yet.</p>`)
    + (state.frame
        ? `<div class="roact">
             <button id="remeasure2">Re-measure this frame</button>
             ${f && !f.scale_known
               ? `<label class="u" for="scaleset">nm/px</label>
                  <input id="scaleset" type="number" step="any" min="0" placeholder="e.g. 52">
                  <button id="scaleapply">Set scale</button>` : ""}
             <span class="u" id="remeasure2out"></span>
           </div>` : "");
  // ...into its OWN element at the end of the pane. Appended to the frame read-out, the
  // four answered questions sat between the conclusions and the image, and they are the
  // same four on every frame -- reference, not a per-frame finding.
  const refEl = $("#refusals");
  if (refEl) refEl.innerHTML = refusals;
  const rb = $("#remeasure2");
  if (rb) rb.onclick = () => remeasure(rb, $("#remeasure2out"));

  // WITHOUT THIS THE APP IS CORRECT AND USELESS. It withholds micrometres when no nm/px is
  // established, which is right, and until now it gave nobody a way to supply the thing it
  // was withholding them for: the scale table is the author's own extracted CSV, keyed by
  // the author's own frame stems. A mask arrives as a PNG and carries no instrument
  // metadata, so for most uploads this control is the only route to a physical unit.
  const sa = $("#scaleapply");
  if (sa) sa.onclick = async () => {
    const v = parseFloat($("#scaleset").value);
    const out = $("#remeasure2out");
    if (!(v > 0)) { out.innerHTML = `<span class="flag bad">nm/px must be above zero</span>`; return; }
    sa.disabled = true; sa.textContent = "Setting…";
    try {
      const q = new URLSearchParams({ arm: state.arm, frame: state.frame, nm_per_px: v });
      const r = await fetch(`/api/scale?${q}`, { method: "POST" });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || r.statusText);
      state.frames = await api(`/api/frames?arm=${encodeURIComponent(state.arm)}` +
        (state.spec ? `&specimen=${encodeURIComponent(state.spec)}` : ""));
      renderFrames(); renderSpecimens(); await renderReadout();
      const fresh = document.getElementById("remeasure2out");
      if (fresh) fresh.innerHTML = `<span class="u">${v} nm/px — micrometre values now shown</span>`;
    } catch (e) {
      out.innerHTML = `<span class="flag bad">${e.message}</span>`;
      sa.disabled = false; sa.textContent = "Set scale";
    }
  };

  // The strip is drawn before the read-out exists on first load, so it is redrawn here
  // once the top statement is known -- otherwise the banner is missing until the next
  // frame change.
  if (typeof STRIP_REC !== "undefined" && STRIP_REC) renderStrip(STRIP_REC);

  el.querySelectorAll(".ro-more").forEach((b) => {
    b.onclick = () => {
      el.querySelectorAll(".ro-line[hidden]").forEach((n) => { n.hidden = false; });
      b.remove();
    };
  });
  el.querySelectorAll(".ro-line").forEach((n) => {
    const open = () => {
      const [h, i] = n.dataset.ro.split(":");
      openDefs((RO[h] || [])[+i]);
    };
    n.onclick = open;
    n.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } };
  });
}

// ---------------------------------------------------------------------------------------
// DEFINITIONS DRAWER. Addressable, persistent, keyboard-reachable and selectable — none of
// which hover text is. Three slots per entry, and the third is the one documentation
// normally omits: when the number lies.
function openDefs(st) {
  $("#defs").hidden = false;
  const body = $("#defsbody");
  if (st) {
    body.innerHTML = `
      <div class="def hi">
        <h5>${st.text}</h5>
        <dl>
          <dt>Basis</dt><dd>${st.basis || "—"}</dd>
          ${st.hedge ? `<dt>When it lies</dt><dd class="lies">${st.hedge}</dd>` : ""}
          ${st.value != null ? `<dt>Value</dt><dd>${typeof st.value === "number" ? (+st.value).toFixed(4) : st.value}</dd>` : ""}
        </dl>
      </div>` + defsAll();
  } else {
    body.innerHTML = defsAll();
  }
  body.scrollTop = 0;
}

const DEFS = [
  ["Crack area fraction", "Crack pixels divided by analysed pixels.",
   "Delesse: an area ratio on a section estimates the volume fraction.",
   "It is the most detector-sensitive number here — CBS reads 2.29× ETD on the same physical field."],
  ["95% CI and ±%", "Sampling interval over fields, and its width as a share of the mean.",
   "ASTM E562-19e1: t(0.975, n−1)·s/√n on between-FIELD variance, n = fields.",
   "It describes this specimen's surface, not the material. Nothing in this arm reaches E562's ±10% target."],
  ["Field vs frame", "A field is one place on the specimen; a frame is one image of it.",
   "56 of 86 gated fields were imaged twice, once through CBS and once through ETD.",
   "Counting frames as fields inflates n by up to 2×, which narrows the interval by √2, and mixes two instruments into one spread."],
  ["Largest share of area", "The biggest connected crack's share of all crack area.",
   "Reported beside the count because 305 components once read as fragmentation while the largest held 97.45%.",
   "Confounded with field size: coarser pixels merge separate cracks, Spearman +0.49 with nm/px."],
  ["P21, P20, P10", "Crack length per area, count per area, and intercepts per probe length.",
   "Dershowitz & Herda (1992): the six Pij densities are incompatible and cannot be unit-converted.",
   "P10 is reported as a MINIMUM over directions, because ASTM B456's criterion is a minimum, not a mean."],
  ["Orientation", "Length-weighted axial direction of the skeleton branches.",
   "Axial statistics on doubled angles, against a 1000-draw permutation null.",
   "Without the null it is meaningless. The null is computed per frame and spans 0.04–1.00 here, because it scales with segment count — a fixed threshold would misread 12 frames."],
  ["MCL bracket", "Longest crack, with and without edge-touching regions.",
   "Reported as a pair because neither end is the value.",
   "Keeping censored regions biases it down; dropping them biases it up, since long cracks reach edges more often."],
  ["Censored share", "How much crack sits in regions touching the field edge.",
   "Weighted by length beside length statistics, by area beside area fraction.",
   "The count share understates it about 5× in SEM and 3× in TXM — that is why the weighting is named."],
  ["Buffon vs skeleton", "Two independent estimates of the same centreline length per area.",
   "L_A = (π/2)·mean(P_L) is skeleton-free, so a disagreement is skeletonisation error.",
   "They differ by ~2.1× on TXM, where cracks are about 3 px wide — there, length is not a measurement."],
  ["Gated vs machine", "Detector output with and without the operator's strokes.",
   "Compared on identical frames, so it is not contaminated by different coverage.",
   "Only 44 of 142 frames carry any correction, and five specimens carry none at all."],
  ["Specks", "Regions too small for a shape to be measurable, counted but not measured.",
   "Threshold is the larger of a pixel floor and a physical one, per frame.",
   "Pixels decide whether a shape is measurable; physical area decides whether two frames excluded the same thing."],
];

function defsAll() {
  return DEFS.map(([t, what, how, lies]) => `
    <div class="def">
      <h5>${t}</h5>
      <dl><dt>Is</dt><dd>${what}</dd>
          <dt>How</dt><dd>${how}</dd>
          <dt>When it lies</dt><dd class="lies">${lies}</dd></dl>
    </div>`).join("");
}

// ---------------------------------------------------------------------------------------
// MARK. The tool that draws the masks this app measures already existed — paint_server.py
// in the SEM repo, with Add crack / Not crack / Erase / Brush / Whole region and Retrain —
// and it was reachable only by knowing it was there and starting it by hand on another
// port. So the app would tell you a mask was unreviewed and say nothing about where to fix
// it. It is started on demand and shown here.
// TWO TOOLS, because they cover different images and the user needs both. "Edit" is this
// app's own canvas: it opens ANY frame the app knows about, including uploads, needs no SEM
// repo, and writes a marked COPY into uploads so research masks stay unwritten. "Full tool"
// is the SEM repo's marking tool -- whole-region flip, undo, reapply, retrain, model
// choice, export -- which only knows that repo's own images.
//
// The full tool now runs INSIDE this window, proxied same-origin at /mark/ (see
// app/mark_proxy.py). It used to be a link that opened the system browser, which undid the
// point of packaging a desktop app at the one step that matters most. An embed was tried
// before and abandoned because a cross-origin iframe rendered blank with no way to see
// inside it; same-origin removes both the blankness and the blindness -- the check below
// reads the tool's own DOM through the frame and says so if it is empty.
//: "full" FIRST, because the first thing a researcher should see is the micrograph with
//: the crack drawn on it -- not the black-and-white mask. The mask is the app's internal
//: representation: an abstraction of the answer, with the specimen it came from thrown
//: away. Opening on it asks the reader to recognise a shape they have not been shown the
//: original of. The full tool opens on the image itself with the crack painted over it,
//: which is the thing being judged.
//:
//: Falls back to "edit" when the full tool cannot run -- no SEM repo, or a frame it does
//: not have -- resolved in renderMark, not here, because availability is not known until
//: /api/paint answers.
let MARK_MODE = "full";

async function renderMark() {
  const el = $("#markbody");
  const paint = await api("/api/paint").catch(() => ({ available: false, why_not: "unreachable" }));
  const head = `<div class="markmodes">
      <button class="seg${MARK_MODE === "edit" ? " on" : ""}" data-mm="edit">Edit mask</button>
      <button class="seg${MARK_MODE === "full" ? " on" : ""}" data-mm="full"
        ${paint.available ? "" : `disabled title="${esc(paint.why_not || "")}"`}>Full tool</button>
      ${MARK_MODE === "full" ? `<span class="u">whole-region flip · undo · reapply · retrain · export</span>` : ""}
    </div>`;

  // FALL BACK RATHER THAN SHOW A DEAD PANE. "full" is the default, and a downloaded copy
  // with no SEM repo cannot run it; landing such a user on a Start button they have no
  // way to satisfy is worse than opening the editor that does work for them.
  if (MARK_MODE === "full" && !paint.available) MARK_MODE = "edit";

  if (MARK_MODE === "full") {
    // DO NOT RE-MOUNT A LIVE TOOL. renderMark runs on every frame pick, and rewriting
    // innerHTML would tear down the iframe and reload the whole application inside it --
    // discarding unsaved strokes and re-fetching a 23 MB template every time the reader
    // clicks a different row. If it is already up, just point it at the new image.
    if (paint.running && $("#markframe")) { wireModes(); syncMarkFrame(); return; }
    el.innerHTML = head + (paint.running
      ? `<p class="note" id="marksync"></p>
         <iframe id="markframe" src="/mark/" title="Marking tool"></iframe>`
      : `<div class="markstate"><p class="markbig">Start the marking tool.</p>
           <button id="markstart" class="upload">Start</button>
           <p class="note" id="markstartout"></p></div>`);
    wireModes();
    const fr = $("#markframe");
    // Follow the app's sidebar, both now and on every later pick. The tool auto-loads
    // its own images[0] as it boots, so this also corrects that first choice.
    if (fr) fr.onload = () => { MARK_LOADED = null; syncMarkFrame(); };
    syncMarkFrame();
    const b = $("#markstart");
    if (b) b.onclick = async () => {
      b.disabled = true; b.textContent = "Starting…";
      try { await api("/api/paint", { method: "POST" }); await renderMark(); }
      catch (e) {
        b.disabled = false; b.textContent = "Start";
        $("#markstartout").innerHTML = `<span class="flag bad">${esc(e.message)}</span>`;
      }
    };
    return;
  }

  if (!state.frame) {
    el.innerHTML = head + `<div class="markstate">
        <p class="markbig">Add an image to mark.</p>
        <p class="note">A black-and-white mask is measured as it is. A .tif is segmented
           first, which needs the SEM repo — see Setup.</p>
      </div>`;
    wireModes();
    return;
  }
  // EVERY FRAME IS MARKABLE, IN THIS WINDOW. Editing a research frame writes a COPY into
  // uploads rather than touching the derived mask, so the loop is one app and the data the
  // app does not own stays unwritten.
  await openEditor(state.frame, head);
  wireModes();
}

//: The tool's own image names, fetched once. It knows only the SEM originals it was
//: pointed at -- not this app's TXM frames, and not anything uploaded here -- so the app
//: has to be able to say "that one is not in the tool" rather than silently showing a
//: different image than the sidebar says.
let MARK_IMAGES = null;
//: The frame this side last asked the tool to open, so a re-sync is not a re-load.
let MARK_LOADED = null;

async function syncMarkFrame() {
  const fr = $("#markframe");
  const note = $("#marksync");
  if (!fr || !note) return;
  if (MARK_IMAGES === null) {
    try { MARK_IMAGES = new Set((await api("/mark/api/images")).map((i) => i.name)); }
    catch (e) { MARK_IMAGES = new Set(); }
  }
  if (!state.frame) {
    note.innerHTML = `<span class="u">Pick an image on the left to mark it.</span>`;
    return;
  }
  // BE HONEST ABOUT WHAT THE TOOL CAN OPEN. Showing its canvas on some other image while
  // the sidebar highlights this one is the two-lists problem in a subtler form: one
  // sidebar, still disagreeing with what is under the brush.
  if (!MARK_IMAGES.has(state.frame)) {
    note.innerHTML = `<span class="flag">${esc(shortFrame(state.frame))}</span> `
      + `<span class="u">is not one of the ${MARK_IMAGES.size} images the full tool was `
      + `pointed at — it reads the SEM originals only. Use <b>Edit mask</b> for this one, `
      + `which works on any frame here.</span>`;
    fr.style.opacity = "0.35";
    return;
  }
  fr.style.opacity = "";
  note.innerHTML = `<span class="u">Marking <b>${esc(shortFrame(state.frame))}</b> — `
    + `chosen on the left. Corrections are written into the SEM repo.</span>`;
  // Same-origin, so the tool's own loader is callable. Calling loadImage rather than
  // clicking its (now hidden) list item means this does not depend on that list's markup.
  // NOT `w.currentImage`: the tool declares it with `let` at the top level of a classic
  // script, which creates a global BINDING and not a property of window, so reading it
  // from here is always undefined and every sync would reload. `function loadImage` is a
  // declaration, so that one IS on window. Track the request on this side.
  try {
    const w = fr.contentWindow;
    if (w && typeof w.loadImage === "function" && MARK_LOADED !== state.frame) {
      MARK_LOADED = state.frame;
      w.loadImage(state.frame);
    }
  } catch (e) { /* not loaded yet; the onload handler calls again */ }
}

function wireModes() {
  document.querySelectorAll("#markbody .markmodes .seg").forEach((b) => {
    b.onclick = () => {
      if (b.disabled || b.dataset.mm === MARK_MODE) return;
      MARK_MODE = b.dataset.mm;
      ED.frame = null;                       // so a return to Edit re-mounts the canvas
      renderMark();
    };
  });
}

// ---------------------------------------------------------------------------------------
// RE-MEASURE, which is what closes the loop. Correcting a mask used to mean a full-corpus
// rebuild -- 358 frames, about 17 minutes -- before you could see what the correction did.
// One frame takes a few seconds, and the reply says what moved, so "did that change
// anything" is answered on the spot rather than being something to go and check.
async function remeasure(btn, where) {
  if (!state.frame) return;
  const was = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Measuring…";
  try {
    const q = new URLSearchParams({ arm: state.arm, frame: state.frame });
    const r = await fetch(`/api/remeasure?${q}`, { method: "POST" });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || r.statusText);
    const ch = Object.entries(d.changed || {});
    const msg = ch.length
      ? `<span class="u">mask written ${d.mask_modified} · </span>` + ch.map(([k, v]) =>
          `<b>${k.replace(/_/g, " ")}</b> ${fmt(v.before, 4)} → ${fmt(v.after, 4)}`).join("  ·  ")
      : `<span class="u">No change — the mask on disk is the same as last measured` +
        ` (written ${d.mask_modified}). Corrections reach it only after the marking tool` +
        ` re-applies and exports.</span>`;

    // Refresh FIRST, then write the message. renderReadout() rebuilds the element the
    // message lives in, so writing it before the refresh silently erased it -- the button
    // worked, the numbers updated, and the user saw nothing happen.
    state.frames = await api(`/api/frames?arm=${encodeURIComponent(state.arm)}` +
      (state.spec ? `&specimen=${encodeURIComponent(state.spec)}` : ""));
    renderFrames();
    renderSpecimens();
    await renderReadout();
    const fresh = document.getElementById(where.id) || where;
    fresh.innerHTML = msg;
  } catch (e) {
    where.innerHTML = `<span class="flag bad">${e.message}</span>`;
  }
  btn.disabled = false;
  btn.textContent = was;
}

// ---------------------------------------------------------------------------------------
// MASK EDITOR, built in, for uploaded frames.
//
// The detect and retrain halves of the loop need the SEM repo's model, which is pickled
// against that repo's interpreter and cannot be bundled -- they stay behind the Mark tab's
// hand-off. Painting on a mask needs no model, and correcting a mask is the step a
// researcher with their own data actually needs, so it is built in and works in a
// downloaded copy.
//
// EDITS ARE MADE AT NATURAL RESOLUTION. The canvas on screen is scaled to fit, but every
// stroke is mapped back to the image's own pixels and drawn on an offscreen canvas at full
// size. Painting on the scaled copy and uploading that would silently resample the user's
// mask, changing every measurement by more than their correction did.
const ED = { img: null, off: null, mode: "add", brush: 24, dirty: false, frame: null };

function editorHTML(frame) {
  return `
    <div class="edbar">
      <button data-ed="add" class="upload">Add crack</button>
      <button data-ed="erase">Erase</button>
      <label class="u" for="edbrush">Brush</label>
      <input id="edbrush" type="range" min="2" max="120" value="${ED.brush}">
      <span class="u" id="edbrushval">${ED.brush}</span>
      <span class="spacer"></span>
      <button id="edsave" class="upload" disabled>Save and re-measure</button>
    </div>
    <p class="note" id="edout">Black is crack. Edits apply at the image's own resolution.</p>
    <canvas id="edcanvas"></canvas>`;
}

async function openEditor(frame, head = "") {
  if (ED.frame === frame && $("#edcanvas")) return;   // already showing this one
  const host = $("#markbody");
  host.innerHTML = head + editorHTML(frame);
  const cv = $("#edcanvas");
  const img = new Image();
  img.crossOrigin = "anonymous";
  await new Promise((res, rej) => {
    img.onload = res; img.onerror = () => rej(new Error("could not load the mask"));
    img.src = `/api/mask/${state.arm}/${encodeURIComponent(frame)}?t=${Date.now()}`;
  }).catch((e) => { $("#edout").innerHTML = `<span class="flag bad">${e.message}</span>`; });
  if (!img.naturalWidth) return;

  ED.img = img; ED.frame = frame; ED.dirty = false;
  ED.off = document.createElement("canvas");
  ED.off.width = img.naturalWidth; ED.off.height = img.naturalHeight;
  ED.off.getContext("2d").drawImage(img, 0, 0);

  const fit = () => {
    const w = Math.min(host.clientWidth - 4, img.naturalWidth);
    cv.width = w; cv.height = Math.round(w * img.naturalHeight / img.naturalWidth);
    cv.getContext("2d").drawImage(ED.off, 0, 0, cv.width, cv.height);
  };
  fit();
  const isUpload = state.arm === "uploads";
  $("#edout").innerHTML = `${img.naturalWidth} × ${img.naturalHeight} px. Black is crack.` +
    (isUpload ? "" :
     ` <span class="u">Saving writes a copy to <b>uploads</b> — ${esc(frame)} itself is` +
     ` not modified.</span>`);

  // Display coordinates map back to the image's own pixels, so a stroke is the same size
  // in the saved mask whatever the window is.
  const toNat = (e) => {
    const r = cv.getBoundingClientRect();
    return [(e.clientX - r.left) / r.width * ED.off.width,
            (e.clientY - r.top) / r.height * ED.off.height];
  };
  let drawing = false, last = null;
  const stroke = (a, b) => {
    const g = ED.off.getContext("2d");
    g.strokeStyle = ED.mode === "add" ? "#000" : "#fff";
    g.lineWidth = ED.brush * (ED.off.width / cv.width);
    g.lineCap = "round"; g.lineJoin = "round";
    g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke();
    cv.getContext("2d").drawImage(ED.off, 0, 0, cv.width, cv.height);
    ED.dirty = true; $("#edsave").disabled = false;
  };
  cv.onpointerdown = (e) => { drawing = true; last = toNat(e); stroke(last, last);
                              cv.setPointerCapture(e.pointerId); };
  cv.onpointermove = (e) => { if (!drawing) return; const n = toNat(e); stroke(last, n); last = n; };
  cv.onpointerup = () => { drawing = false; };
  cv.onpointerleave = () => { drawing = false; };

  host.querySelectorAll("[data-ed]").forEach((b) => {
    b.onclick = () => {
      ED.mode = b.dataset.ed;
      host.querySelectorAll("[data-ed]").forEach((x) =>
        x.classList.toggle("upload", x.dataset.ed === ED.mode));
    };
  });
  $("#edbrush").oninput = (e) => { ED.brush = +e.target.value; $("#edbrushval").textContent = ED.brush; };

  $("#edsave").onclick = async () => {
    const btn = $("#edsave"), out = $("#edout");
    btn.disabled = true; btn.textContent = "Saving…";
    try {
      const blob = await new Promise((r) => ED.off.toBlob(r, "image/png"));
      const fd = new FormData();
      fd.append("file", blob, `${frame}_gated.png`);
      const q = new URLSearchParams({ arm: state.arm, frame });
      const r = await fetch(`/api/mask_edit?${q}`, { method: "POST", body: fd });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || r.statusText);
      const ch = Object.entries(d.changed || {});
      out.innerHTML = ch.length
        ? ch.map(([k, v]) => `<b>${k.replace(/_/g, " ")}</b> ${fmt(v.before, 4)} → ${fmt(v.after, 4)}`).join("  ·  ")
        : `<span class="u">Saved. No measurement changed.</span>`;
      ED.dirty = false;
      if (d.copied_from) {
        // The edit became a new frame in another arm. Follow it, or the user is looking at
        // the original while reading numbers that belong to their copy.
        out.innerHTML = `<span class="u">Saved as <b>${esc(d.frame)}</b> in uploads` +
          ` (${esc(d.copied_from)} unchanged).</span> ` + out.innerHTML;
        state.arm = "uploads"; state.spec = ""; state.frame = d.frame;
        $("#arm").value = "uploads";
        await loadArm();
        selectFrame(d.frame);
        return;
      }
      state.frames = await api(`/api/frames?arm=${encodeURIComponent(state.arm)}` +
        (state.spec ? `&specimen=${encodeURIComponent(state.spec)}` : ""));
      renderFrames(); renderSpecimens(); renderReadout();
    } catch (e) {
      out.innerHTML = `<span class="flag bad">${e.message}</span>`;
    }
    btn.textContent = "Save and re-measure";
    btn.disabled = !ED.dirty;
  };
}

async function loadArm() {
  try {
    state.frames = await api(`/api/frames?arm=${encodeURIComponent(state.arm)}` +
      (state.spec ? `&specimen=${encodeURIComponent(state.spec)}` : ""));
  } catch (e) {
    // CLEAR THE VIEW, do not leave it. This used to write the message and return, so
    // state.frames, the frame table, the specimen dropdown and the detail pane all stayed
    // on the PREVIOUS arm while state.arm and the visible selector had already moved --
    // one arm's data under another arm's label, which is exactly the mixture the API
    // refuses to produce because the arms are different instruments. Clicking a row then
    // requested that frame's mask from the new arm and got a 404, and overwrote the one
    // diagnostic on the page.
    state.frames = []; state.frame = null;
    renderFrames();
    $("#spec").innerHTML = `<option value="">all</option>`;
    $("#detail").querySelectorAll(".pane").forEach((el) => { el.innerHTML = ""; });
    $("#listcount").textContent = "";
    $("#strip").innerHTML = `<span class="flag bad">Could not load the ${esc(state.arm)} `
      + `arm — ${esc(e.message)}. Nothing below is showing another arm's numbers; `
      + `pick an arm again to retry.</span>`;
    return;
  }
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
  $("#listcount").textContent = noScale
    ? `${noScale}/${state.frames.length} frames: no scale, µm withheld`
    : `all ${state.frames.length} frames scaled`;
  renderFrames();
  renderSpecimens();
  renderReadout();
  if (typeof window.figRenderRef === "function") window.figRenderRef();
  if (state.frames.length) selectFrame(state.frames[0].frame);
}

(async function () {
  // No theme toggle and no system-appearance following: the stylesheet is one fixed dark
  // palette now. Following the OS meant the same app looked different on two machines and
  // different on one machine at sunset, and the marking tool embedded in Mark is
  // dark-themed regardless, so a light shell around it read as two applications.
  // Pass the filters the screen is applying. Without them a filtered view exported
  // unfiltered rows, and the file carried no record of what had been excluded.
  $("#csv").onclick = () => {
    const q = new URLSearchParams({ arm: state.arm, level: "frames" });
    if (state.spec) q.set("specimen", state.spec);
    download(`/api/export.csv?${q}`,
             `${state.arm.replace("/", "_")}${state.spec ? "_" + state.spec : ""}_frames.csv`);
  };
  // Upload. A .tif is segmented here first; a .png is taken as a mask already. The control
  // says "image or mask" rather than explaining the difference, because the server decides
  // from the extension and the user should not have to.
  // BATCH. The input took one file and the handler read files[0], so a researcher with a
  // folder of masks uploaded them one at a time. Sequential rather than parallel: each
  // upload measures a full frame, and a dozen at once would compete for the same cores
  // and make every one slower.
  $("#up").onchange = async (e) => {
    const files = [...e.target.files];
    if (!files.length) return;
    const lbl = document.querySelector(".upload[for=up]") || document.querySelector(".upload");
    const was = lbl.textContent;
    lbl.setAttribute("aria-busy", "true");
    const done = [], failed = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      lbl.textContent = files.length > 1
        ? `${i + 1} of ${files.length}…` : (/\.tiff?$/i.test(f.name) ? "segmenting…" : "measuring…");
      const fd = new FormData();
      fd.append("file", f);
      try {
        const r = await fetch("/api/upload", { method: "POST", body: fd });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || r.status);
        done.push(d.frame);
      } catch (err) {
        failed.push(`${f.name}: ${err.message}`);
      }
    }
    lbl.removeAttribute("aria-busy");
    lbl.textContent = was;
    e.target.value = "";

    state.arm = "uploads"; state.spec = "";
    const arms = await api("/api/arms");
    $("#arm").innerHTML = arms.map((a) =>
      `<option value="${a.arm}"${a.arm === "uploads" ? " selected" : ""}>${a.arm} · ${a.n_frames} frames</option>`).join("");
    await loadArm();
    if (done.length) selectFrame(done[done.length - 1]);
    // Say what failed, per file. A batch that silently drops one is worse than a batch
    // that refuses: the count looks right and a measurement is missing.
    $("#listcount").innerHTML = failed.length
      ? `<span class="flag bad">${done.length} added, ${failed.length} refused</span>`
      : "";
    if (failed.length) console.warn("uploads refused:\n" + failed.join("\n"));
  };

  // RESTORED. This whole block was deleted as collateral by 977e28c, a commit about crack
  // pins and batch upload whose message never mentions figures: the batch-upload rewrite
  // spliced into the handler immediately above and its anchors swallowed the figure
  // builder that followed it. The markup kept rendering, so the Figure tab shipped for
  // several releases as two empty dropdowns and a download button that did nothing, while
  // app/figures.py and /api/figure.svg stayed fully alive behind it. Five of six audit
  // dimensions found it independently. See tests/test_figures.py for the guard that now
  // fails when an id declared in the Figure pane is referenced by no JavaScript.
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
    // Thin specimens are always included now. The checkbox asked the reader to settle a
    // statistics question by clicking, and the two answers are not equally defensible:
    // either those specimens are admissible, in which case show them with their n, or they
    // are not, in which case hiding them behind an opt-in is worse than excluding them.
    // The figure labels n per specimen, so a box built on two fields announces itself.
    q.set("include_thin", "true");
    out.innerHTML = `<p class="note">drawing…</p>`;
    const r = await fetch(`/api/figure.svg?${q}`);
    if (!r.ok) {
      let d = {}; try { d = await r.json(); } catch (_) {}
      out.innerHTML = `<p class="note"><span class="flag">${d.detail || "could not draw this"}</span></p>`;
      return;
    }
    out.innerHTML = await r.text();
    // WHAT THE FIGURE SHOWS, under the figure. A plot builder that renders a picture and
    // says nothing about it leaves the reading to whoever is looking, which is the same
    // gap the Compare table had. Fetched with the same parameters, from the same build,
    // so the sentences cannot disagree with the points above them.
    try {
      const said = await api(`/api/figure/says?${q}`);
      FIG_SAID = said.statements || [];
      if (FIG_SAID.length) {
        out.insertAdjacentHTML("beforeend", `<div class="ro figro">` + FIG_SAID.map((st, i) =>
          `<div class="ro-line ${st.level}" data-figro="${i}" tabindex="0" role="button">
             <span class="mk">${MARK[st.level] || "\u00b7"}</span>
             <span class="tx">${esc(st.text)}</span>
             <span class="who">THIS FIGURE</span>
           </div>`).join("") + `</div>`);
        out.querySelectorAll("[data-figro]").forEach((el) => {
          const open = () => openDefs(FIG_SAID[+el.dataset.figro]);
          el.onclick = open;
          el.onkeydown = (e) => {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
          };
        });
      }
    } catch (e) { /* the picture is still worth showing without them */ }
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
    ["figkind", "figy", "figx"].forEach((id) => $("#" + id).onchange = figRender);
  } catch (e) { $("#figout").innerHTML = `<p class="note">figures unavailable: ${e.message}</p>`; }

  wireTabs();
  $("#defsbtn").onclick = () => {
    const d = $("#defs");
    if (d.hidden) { openDefs(null); } else { d.hidden = true; }
  };
  $("#defsclose").onclick = () => { $("#defs").hidden = true; };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") $("#defs").hidden = true;
  });
  // A 142-row list needs a filter, and a filter is cheaper than any navigation.
  $("#search").oninput = (e) => {
    const q = e.target.value.trim().toLowerCase();
    let n = 0;
    $("#frames").querySelectorAll("tbody tr").forEach((tr) => {
      if (tr.classList.contains("grp")) return;      // handled after, by child count
      const hit = !q || tr.dataset.f?.toLowerCase().includes(q);
      tr.hidden = !hit;
      if (hit) n++;
    });
    $("#listcount").textContent = q ? `${n}` : "";
  };

  await wireSetup();
  try { await health(); } catch (e) { /* the page still works without it */ }

  let arms;
  // No dataset is the normal first launch of a downloaded copy, not a failure. Open Setup
  // and say the one thing that is true: you can start by adding an image.
  //
  // AN EMPTY ARRAY IS THE SAME STATE AS THE 503, and it used not to be. Once the dataset
  // files exist but hold no records, /api/arms stops 503ing and returns [] with a 200, so
  // this catch was skipped and `arms[0].arm` on the next line threw -- taking with it
  // everything after it in this function, including showSetup(true) and both sentences
  // below. The first-run screen went blank and stayed blank across restarts, and the
  // reachable trigger was one click on a visible button (see analysis/batch.py, which no
  // longer writes an empty dataset over a good one).
  const firstRun = () => {
    showSetup(true);
    $("#strip").innerHTML = `<span class="who">No measurements yet.</span>`;
    $("#listcount").textContent = "Add a mask or micrograph above to measure one, " +
      "or point the app at a SEM repo in Setup.";
  };
  try { arms = await api("/api/arms"); }
  catch (e) { firstRun(); return; }
  if (!arms || !arms.length) { firstRun(); return; }
  $("#arm").innerHTML = arms.map((a) =>
    `<option value="${a.arm}">${a.arm} · ${a.n_frames} frames</option>`).join("");
  state.arm = arms[0].arm;
  // No total-count subtitle any more. The arm dropdown carries its own count and the strip
  // carries the number people actually cite, so a third tally of the same corpus was words
  // for their own sake.
  if (HEALTH && !HEALTH.sem_repo) showSetup(true);
  $("#arm").onchange = (e) => { state.arm = e.target.value; state.spec = ""; loadArm(); };
  $("#spec").onchange = (e) => { state.spec = e.target.value; loadArm(); };
  loadArm();
})();
