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
    let msg = `${r.status}`;
    try { msg = (await r.json()).detail || msg; } catch (_) {}
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

function shortFrame(name) {
  return (FRAME_PREFIX && name.startsWith(FRAME_PREFIX) &&
          name.length > FRAME_PREFIX.length + 2)
    ? name.slice(FRAME_PREFIX.length) : name;
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
  t.querySelector("tbody").innerHTML = rows.map((f) => {
    // A frame with no scale cannot contribute to any physical statistic. Say so in the row
    // rather than showing a blank cell that reads as zero.
    // NO ECHO TOOLTIPS. There were 346 of these across 142 rows, 1,668 words -- more
    // hidden text than the entire visible page -- and every one restated the cell it sat
    // on: the frame stem in a title over a cell showing the frame stem, and the same
    // specks sentence repeated 142 times. What they meant now lives once, in the
    // definitions drawer, where it is addressable and reachable without a mouse.
    const noScale = f.scale_known ? "" : ` <span class="flag">no scale</span>`;
    return `<tr data-f="${f.frame}" aria-selected="${state.frame === f.frame}">` +
      FCOLS.map(([k]) => {
        if (k === "frame") {
          // DROP THE PREFIX THE ROWS SHARE. The list held 653 of the page's 840 words, and
          // most of that was one string repeated: every row of MAR_AmbB_HIP begins with
          // "MAR_AmbB_HIP_". The specimen is named in the selector directly above, so the
          // prefix is redundant with it -- removing it cuts the list's text by more than
          // half with no information lost, and the full stem is still what the row carries
          // in data-f, what the CSV exports and what the Frame detail tab shows.
          return `<td>${esc(shortFrame(f[k]))}${noScale}</td>`;
        }
        if (k === "_cracks") {
          // One cell, because a count without its speck count invites the fragmentation
          // misreading this project has already made once.
          const sp = f.speck_count ? ` <span class="muted">+${f.speck_count.toLocaleString()}</span>` : "";
          return `<td>${fmt(f.n_cracks_measured)}${sp}</td>`;
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
    ["R_L median", f.R_L_median === null || f.R_L_median === undefined ? "—"
      : `${fmt(f.R_L_median, 3)} <span class="muted">axis ${f.R_L_axis_deg}°, ${fmt(f.R_L_n_segments)} segments</span>`],
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

  $("#mask").hidden = false;
  $("#mask").src = `/api/mask/${state.arm}/${encodeURIComponent(name)}`;
  $("#mask").alt = `Crack mask for ${name}`;
  $("#masknote").textContent = `${state.arm} — black is crack.`;

  rose(f.orientation_hist_deg);
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
     ci ? `<span class="big">${pct(ci.mean)}</span> <span class="ci">95% CI ${ciLo(ci)}–${pct(ci.ci95_hi)}, ${ci.n_fields} fields</span>${raBadge(ci)}`
        : `<span class="big">${pct(r.area_fraction_median)}</span> <span class="ci">median of ${r.n_fields} field${r.n_fields > 1 ? "s" : ""} — under 3, no interval</span>`],
    ["P10", `${num(r.p10_min_per_mm)} <span class="u">/mm min</span> · ${num(r.p10_mean_per_mm)} <span class="u">/mm mean</span>`],
    ["P21 · P20", `${num(r.p21_skeleton_mm_per_mm2)} <span class="u">mm/mm²</span> · ${num(r.p20_per_mm2, 0)} <span class="u">/mm²</span>`],
    // null / 1000 is 0 in JavaScript, so an unscaled specimen was reporting "0.00 mm" of
    // total crack length -- a measured zero where the truth is "not measurable".
    // MCL here is the longest tip-to-tip crack, not the largest network's total
    // centreline; the two are separate columns since they stopped being the same number.
    ["MCL · TCL", `${num(r.mcl_um)} <span class="u">µm</span> · ${num(r.tcl_um_total == null ? null : r.tcl_um_total / 1000, 2)} <span class="u">mm</span>`],
    ["Largest network", `${num(r.largest_network_centreline_um)} <span class="u">µm centreline</span>`],
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
      `<td>${ci ? `${ciLo(ci)}–${pct(ci.ci95_hi)}` : "<span class='u'>n&lt;3</span>"}</td>` +
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
const TABS = [
  ["mark", "Mark"],
  ["analysis", "Analysis"],
  ["compare", "Compare"],
  ["figure", "Figure"],
];
let TAB = "mark";

function showTab(id) {
  TAB = id;
  TABS.forEach(([k]) => { $("#pane-" + k).hidden = k !== id; });
  $("#tabs").querySelectorAll("button").forEach((b) =>
    b.setAttribute("aria-selected", String(b.dataset.tab === id)));
  // The figure is expensive and the rose needs a laid-out box, so both render on reveal
  // rather than on every frame change.
  if (id === "figure" && typeof window.figRenderRef === "function") window.figRenderRef();
  if (id === "mark") renderMark();
  if (id === "analysis") rose(
    (state.frames.find((x) => x.frame === state.frame) || {}).orientation_hist_deg);
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
function renderStrip(rec) {
  const el = $("#strip");
  if (!rec) { el.innerHTML = `<span class="who">Select a specimen.</span>`; return; }
  const ci = rec.area_fraction_ci;
  const ds = rec.detector_sensitivity;
  const a = rec.arm_sensitivity;
  const bits = [
    `<span class="who">${rec.specimen}</span>`,
    ci ? `<span class="big">${pct(ci.mean)}</span>` : `<span class="big">${pct(rec.area_fraction_median)}</span>`,
    `<span class="u">crack area</span>`,
    ci ? `<span class="ci">95% CI ${ciLo(ci)}–${pct(ci.ci95_hi)}</span>${raBadge(ci)}`
       : `<span class="ci">no interval, ${rec.n_fields} field${rec.n_fields === 1 ? "" : "s"}</span>`,
    `<span class="u">${rec.n_fields} fields${rec.n_frames !== rec.n_fields ? ` / ${rec.n_frames} frames` : ""}</span>`,
  ];
  if (ds && Math.abs(ds.cbs_over_etd_median - 1) > 0.2) {
    bits.push(`<span class="banner bad" title="CBS against ETD on ${ds.n_fields_both_detectors} fields imaged both ways. Detector is confounded with specimen here.">detector ×${ds.cbs_over_etd_median}</span>`);
  }
  if (a && !a.n_frames_corrected) {
    bits.push(`<span class="banner" title="The gated and machine arms are identical on all ${a.n_paired_frames} frames of this specimen.">no human review</span>`);
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

  const body = roRender(RO);
  // ONE LINE, NOT THREE BLOCKS. The refusals were 51 words permanently on screen -- more
  // than the read-out they sit under -- restating three questions the reader may not have
  // asked. They still must be STATED rather than silently omitted, because the mode
  // question recurs precisely when nothing addresses it; they just do not need to be the
  // largest thing on the page. One summary line, expanding to the same content.
  const refusals = (d.refusals || []).length ? `
    <details class="refuse-all">
      <summary>Not determinable here: ${(d.refusals || []).map((r) =>
        r.question.replace(/\?.*$/, "").replace(/^(Transgranular or intergranular)$/, "crack mode")
         .replace(/^Ductile or brittle.*$/, "fracture mode").replace(/^Crack depth.*$/, "depth")
         .toLowerCase()).join(" · ")}</summary>
      ${(d.refusals || []).map((r) => `
        <div class="refuse">
          <h4>${r.question}</h4>
          <div class="ans">${r.answer}</div>
          <details><summary>Why, and what would answer it</summary>
            <p>${r.why}</p>
            ${r.would_need && r.would_need.length
              ? `<ul>${r.would_need.map((x) => `<li>${x}</li>`).join("")}</ul>` : ""}
            ${r.not_this ? `<p><strong>Not this:</strong> ${r.not_this}</p>` : ""}
          </details>
        </div>`).join("")}
    </details>` : "";

  el.innerHTML = (body || `<p class="ro-empty">Nothing this data supports saying yet.</p>`)
    + (state.frame
        ? `<div class="roact">
             <button id="remeasure2">Re-measure this frame</button>
             ${f && !f.scale_known
               ? `<label class="u" for="scaleset">nm/px</label>
                  <input id="scaleset" type="number" step="any" min="0" placeholder="e.g. 52">
                  <button id="scaleapply">Set scale</button>` : ""}
             <span class="u" id="remeasure2out"></span>
           </div>` : "")
    + refusals;
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
let MARK_URL = null;

async function renderMark() {
  const el = $("#markbody");
  if (!state.frame) {
    el.innerHTML = `<div class="markstate">
        <p class="markbig">Add an image to mark.</p>
        <p class="note">A black-and-white mask is measured as it is. A .tif is segmented
           first, which needs the SEM repo — see Setup.</p>
      </div>`;
    return;
  }
  // EVERY FRAME IS MARKABLE, IN THIS WINDOW. Editing a research frame writes a COPY into
  // uploads rather than touching the derived mask, so the loop is one app and the data the
  // app does not own stays unwritten.
  return openEditor(state.frame);
}

function mountMark(url) {
  MARK_URL = url;
  // A HAND-OFF, NOT AN EMBED. The iframe loaded -- 750 px tall, HTTP 200, no blocking
  // header, no console error -- and rendered blank. It is cross-origin (a different port),
  // so there is no way to see inside it and find out why, and I am not going to ship a
  // frame I cannot verify: a blank panel is worse for navigation than a plain link, which
  // was the complaint in the first place.
  //
  // What this tab has to fix is that the tool was UNDISCOVERABLE. A named tab, a live
  // status and one click does that. Embedding it properly would mean reverse-proxying the
  // whole Flask app through this one to make it same-origin, which is a lot of surface for
  // a canvas that POSTs image layers.
  $("#markbody").innerHTML = `
    <div class="markstate">
      <p class="markbig">Marking tool is running.</p>
      <a href="${url}" target="_blank" rel="noopener"><button class="upload">Open marking tool</button></a>
      <p class="note">Red = crack, cyan = not crack.</p>
      <p class="markbig" style="margin-top:14px">When the mask looks right</p>
      <button id="remeasure1" class="upload">Re-measure this frame</button>
      <p class="note" id="remeasure1out"></p>
    </div>`;
  const b = $("#remeasure1");
  if (b) b.onclick = () => remeasure(b, $("#remeasure1out"));
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

async function openEditor(frame) {
  if (ED.frame === frame && $("#edcanvas")) return;   // already showing this one
  const host = $("#markbody");
  host.innerHTML = editorHTML(frame);
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
    $("#strip").innerHTML = `<span class="flag bad">${e.message}</span>`;
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
  // The theme toggle is gone: a macOS app should follow system appearance, and the
  // stylesheet already implements prefers-color-scheme, so the button existed to
  // demonstrate the CSS.
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
      $("#listcount").textContent =
        `${d.frame}: ${d.n_cracks.toLocaleString()} cracks, ${d.n_specks.toLocaleString()} specks — ${d.note}` +
        (d.scale_known ? "" : " · no scale, so µm is withheld");
    } catch (err) {
      lbl.textContent = was;
      $("#listcount").innerHTML = `<span class="flag bad">upload failed: ${err.message}</span>`;
    } finally {
      lbl.removeAttribute("aria-busy");
      e.target.value = "";
    }
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
      const hit = !q || tr.dataset.f?.toLowerCase().includes(q);
      tr.hidden = !hit;
      if (hit) n++;
    });
    $("#listcount").textContent = q ? `${n}` : "";
  };

  await wireSetup();
  try { await health(); } catch (e) { /* the page still works without it */ }

  let arms;
  try { arms = await api("/api/arms"); }
  catch (e) {
    // No dataset is the normal first launch of a downloaded copy, not a failure. Open Setup
    // and say the one thing that is true: you can start by adding an image.
    showSetup(true);
    $("#strip").innerHTML = `<span class="who">No measurements yet.</span>`;
    $("#listcount").textContent = "Add a mask or micrograph above to measure one, " +
      "or point the app at a SEM repo in Setup.";
    return;
  }
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
