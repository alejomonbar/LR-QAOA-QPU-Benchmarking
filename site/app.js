/* LR-QAOA QPU Benchmark — renders site/data/results.json (built by scripts/build_site_data.py). No dependencies. */
(function () {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const NS = "http://www.w3.org/2000/svg";
  const TOPO = { FC: "fully connected", NL: "native layout", "1D": "1D chain" };
  const SLOTS = ["var(--s1)", "var(--s2)", "var(--s3)"];
  const MAX_PICK = 3;

  /* ---------- theme ---------- */
  const root = document.documentElement;
  try { const t = localStorage.getItem("theme"); if (t) root.dataset.theme = t; } catch (e) {}
  $("#themeBtn").addEventListener("click", () => {
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch (e) {}
  });

  /* ---------- formatting ---------- */
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const fDate = (s) => { if (!s) return "–"; const [y, m, d] = s.split("-").map(Number); return `${d} ${MONTHS[m - 1]} ${y}`; };
  const fInt = (n) => (n == null ? "–" : Math.round(n).toLocaleString("en-US"));
  const f3 = (n) => (n == null ? "–" : n.toFixed(3));
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const status = (r) => r.passes === true ? `<span class="st ok">✓ above random</span>`
    : r.passes === false ? `<span class="st no">✗ not above random</span>` : `<span class="st na">– no random baseline</span>`;

  /* ---------- tooltip ---------- */
  const tip = $("#tip");
  function showTip(html, x, y) {
    tip.innerHTML = html; tip.hidden = false;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    let left = x + 14, top = y + 14;
    if (left + w > innerWidth - 8) left = x - w - 14;
    if (top + h > innerHeight - 8) top = y - h - 14;
    tip.style.left = Math.max(8, left) + "px"; tip.style.top = Math.max(8, top) + "px";
  }
  const hideTip = () => { tip.hidden = true; };

  /* ---------- scales & ticks ---------- */
  function niceTicks(a, b, n = 5) {
    const step0 = (b - a) / n, mag = 10 ** Math.floor(Math.log10(step0)), e = step0 / mag;
    const step = (e >= 7.5 ? 10 : e >= 3.5 ? 5 : e >= 1.5 ? 2 : 1) * mag, out = [];
    for (let v = Math.ceil(a / step - 1e-9) * step; v <= b + 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }
  function logTicks(a, b) {
    const lo = Math.floor(Math.log10(a)), hi = Math.ceil(Math.log10(b)), mults = hi - lo <= 2 ? [1, 2, 5] : [1, 3], out = [];
    for (let e = lo; e <= hi; e++) for (const m of mults) { const v = m * 10 ** e; if (v >= a * 0.999 && v <= b * 1.001) out.push(v); }
    return out;
  }
  const el = (tag, attrs = {}, parent) => {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  };

  /* ---------- generic line/dot chart ----------
     series: [{ key, label, color (null = context), pts: [{x, y, hollow, run}] }] */
  function lineChart(host, cfg) {
    const draw = () => {
      host.innerHTML = "";
      const W = host.clientWidth, H = host.clientHeight;
      if (!W || !H) return;
      const m = { t: 12, r: 18, b: 44, l: 52 };
      const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": cfg.aria || "" }, host);
      const all = cfg.series.flatMap((s) => s.pts);
      if (!all.length) { el("text", { x: W / 2, y: H / 2, "text-anchor": "middle", class: "empty" }, svg).textContent = "No runs to show"; return; }
      let [x0, x1] = cfg.xDomain || [Math.min(...all.map((p) => p.x)), Math.max(...all.map((p) => p.x))];
      let [y0, y1] = cfg.yDomain || [Math.min(...all.map((p) => p.y)), Math.max(...all.map((p) => p.y))];
      (cfg.refs || []).forEach((r) => { y0 = Math.min(y0, r.y); y1 = Math.max(y1, r.y); });
      if (cfg.xLog) { x0 /= 1.15; x1 *= 1.15; } else { const pad = (x1 - x0 || 1) * 0.04; x0 -= pad; x1 += pad; }
      const yPad = (y1 - y0 || 0.1) * 0.08; y0 -= yPad; y1 += yPad;
      const X = cfg.xLog ? (v) => m.l + (Math.log10(v) - Math.log10(x0)) / (Math.log10(x1) - Math.log10(x0)) * (W - m.l - m.r)
                         : (v) => m.l + (v - x0) / (x1 - x0) * (W - m.l - m.r);
      const Y = (v) => H - m.b - (v - y0) / (y1 - y0) * (H - m.t - m.b);

      const grid = el("g", { class: "grid" }, svg), axis = el("g", { class: "axis" }, svg);
      niceTicks(y0, y1, Math.max(3, Math.round((H - m.t - m.b) / 60))).forEach((v) => {
        el("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v) }, grid);
        el("text", { x: m.l - 8, y: Y(v) + 4, "text-anchor": "end" }, axis).textContent = cfg.yFmt ? cfg.yFmt(v) : v.toFixed(2);
      });
      const xt = cfg.xLog ? logTicks(x0 * 1.15, x1 / 1.15) : niceTicks(x0, x1, Math.max(3, Math.round((W - m.l - m.r) / 80)));
      xt.forEach((v) => {
        el("line", { x1: X(v), x2: X(v), y1: m.t, y2: H - m.b }, grid);
        el("text", { x: X(v), y: H - m.b + 17, "text-anchor": "middle" }, axis).textContent = fInt(v);
      });
      el("text", { x: (m.l + W - m.r) / 2, y: H - 6, "text-anchor": "middle", class: "title" }, axis).textContent = cfg.xLabel;
      el("text", { x: -(m.t + H - m.b) / 2, y: 14, transform: "rotate(-90)", "text-anchor": "middle", class: "title" }, axis).textContent = cfg.yLabel;

      (cfg.refs || []).forEach((r) => {
        el("line", { x1: m.l, x2: W - m.r, y1: Y(r.y), y2: Y(r.y), class: "ref" }, svg);
      });
      const labels = el("g", {}, svg); // drawn after the data so they sit on top (with a halo)
      const drawRefLabels = () => (cfg.refs || []).forEach((r) => {
        el("text", { x: m.l + 6, y: Y(r.y) + 15, class: "ref-label" }, labels).textContent = r.label;
      });

      const ordered = [...cfg.series.filter((s) => !s.color), ...cfg.series.filter((s) => s.color)];
      const hit = [];
      ordered.forEach((s) => {
        const g = el("g", {}, svg), emph = !!s.color, col = s.color || "var(--ctx)";
        const pts = [...s.pts].sort((a, b) => a.x - b.x);
        if (pts.length > 1) el("path", { d: pts.map((p, i) => `${i ? "L" : "M"}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join(""), fill: "none", stroke: col, "stroke-width": emph ? 2 : 1.2, "stroke-linejoin": "round", "stroke-linecap": "round" }, g);
        pts.forEach((p) => {
          const cx = X(p.x), cy = Y(p.y);
          if (emph || pts.length === 1 || cfg.ctxDots) {
            el("circle", { cx, cy, r: emph ? 4.5 : 3, fill: p.hollow ? "var(--card)" : col, stroke: p.hollow ? col : "var(--card)", "stroke-width": 2 }, g);
          }
          hit.push({ cx, cy, s, p, emph });
        });
      });
      svg.appendChild(labels); drawRefLabels();
      const ring = el("circle", { r: 7, fill: "none", stroke: "var(--ink)", "stroke-width": 1.5, visibility: "hidden" }, svg);
      const nearest = (ev) => {
        const b = svg.getBoundingClientRect(), mx = (ev.clientX - b.left) * W / b.width, my = (ev.clientY - b.top) * H / b.height;
        let best = null, bd = 26 * 26;
        for (const h of hit) { const d = (h.cx - mx) ** 2 + (h.cy - my) ** 2 - (h.emph ? 60 : 0); if (d < bd) { bd = d; best = h; } }
        return best;
      };
      svg.addEventListener("pointermove", (ev) => {
        const h = nearest(ev);
        if (!h) { ring.setAttribute("visibility", "hidden"); hideTip(); svg.style.cursor = ""; return; }
        ring.setAttribute("cx", h.cx); ring.setAttribute("cy", h.cy); ring.setAttribute("visibility", "visible");
        svg.style.cursor = cfg.onPick ? "pointer" : "";
        showTip(cfg.tip(h.s, h.p), ev.clientX, ev.clientY);
      });
      svg.addEventListener("pointerleave", () => { ring.setAttribute("visibility", "hidden"); hideTip(); });
      if (cfg.onPick) svg.addEventListener("click", (ev) => { const h = nearest(ev); if (h) cfg.onPick(h.s.key); });
    };
    draw();
    return draw;
  }
  function autoRedraw(host, fn) {
    let w = host.clientWidth;
    new ResizeObserver(() => { if (host.clientWidth !== w) { w = host.clientWidth; fn(); } }).observe(host);
  }

  /* ---------- selection with stable colors (color follows the entity) ---------- */
  function Picker(onChange) {
    const slot = new Map(); // key -> slot index
    return {
      has: (k) => slot.has(k),
      color: (k) => (slot.has(k) ? SLOTS[slot.get(k)] : null),
      keys: () => [...slot.keys()],
      set(keys) { slot.clear(); keys.slice(0, MAX_PICK).forEach((k, i) => slot.set(k, i)); },
      keepOnly(valid) { [...slot.keys()].forEach((k) => { if (!valid(k)) slot.delete(k); }); },
      toggle(k) {
        if (slot.has(k)) slot.delete(k);
        else {
          if (slot.size >= MAX_PICK) slot.delete(slot.keys().next().value);
          const used = new Set(slot.values()); let i = 0; while (used.has(i)) i++;
          slot.set(k, i);
        }
        onChange();
      },
    };
  }
  function renderChips(host, items, picker) {
    host.innerHTML = "";
    items.forEach(({ key, label }) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "chip"; b.setAttribute("aria-pressed", picker.has(key));
      b.innerHTML = `<i style="background:${picker.color(key) || "var(--ctx)"}"></i>${esc(label)}`;
      b.addEventListener("click", () => picker.toggle(key));
      host.appendChild(b);
    });
  }
  function renderLegend(host, picker, labelOf, extra = "") {
    host.innerHTML = picker.keys().map((k) => `<span><i style="background:${picker.color(k)}"></i>${esc(labelOf(k))}</span>`).join("")
      + `<span><i style="background:var(--ctx)"></i>other runs</span>` + extra;
  }

  /* ---------- main ---------- */
  fetch("data/results.json", { cache: "no-cache" })
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(render)
    .catch((e) => { $("#kSrc").textContent = "Could not load results (" + e.message + "). Run scripts/build_site_data.py first."; });

  function render(data) {
    const DEV = data.devices, RUNS = data.runs;
    const dev = (r) => DEV[r.device] || { name: r.device, kind: "qpu" };
    const runLabel = (r) => dev(r).name + (r.variant ? ` (${r.variant})` : "");
    const isQpu = (r) => dev(r).kind === "qpu";
    const qpuRuns = RUNS.filter(isQpu);
    const gatesTip = (r, p) => (r.edges ? `<br><span class="k">2-qubit gates at p=${p}:</span> ${fInt(p * r.edges)}` : "");

    /* key figures */
    const qpus = new Set(qpuRuns.map((r) => r.device));
    $("#kQpu").textContent = qpus.size;
    $("#kVendor").textContent = new Set([...qpus].map((d) => DEV[d].vendor)).size;
    const fcBest = qpuRuns.filter((r) => r.topology === "FC" && r.passes).sort((a, b) => b.nq - a.nq)[0];
    if (fcBest) { $("#kFc").textContent = fcBest.nq + " q"; $("#kFcLbl").textContent = `largest fully connected problem above random (${dev(fcBest).name})`; }
    const deep = qpuRuns.filter((r) => r.gates_at_deepest).sort((a, b) => b.gates_at_deepest - a.gates_at_deepest)[0];
    if (deep) { $("#kGates").textContent = fInt(deep.gates_at_deepest); $("#kGatesLbl").textContent = `2-qubit gates in the deepest run above random (${runLabel(deep)}, ${TOPO[deep.topology]}, p = ${fInt(deep.deepest_p_above_random)})`; }
    const newest = qpuRuns.map((r) => r.date).sort().pop();
    $("#kSrc").textContent = `${RUNS.length} runs on ${Object.keys(DEV).length} devices and simulators · newest result ${fDate(newest)}`;
    $("#buildInfo").textContent = `Built ${data.generated.replace("T", " ").slice(0, 16)} UTC` + (data.commit ? ` from commit ${data.commit}` : "");

    /* latest feed: one card per device and day, summarised per graph type */
    const groups = {};
    qpuRuns.forEach((r) => { const k = r.device + "|" + r.date; (groups[k] = groups[k] || []).push(r); });
    const feed = Object.values(groups).sort((a, b) => b[0].date.localeCompare(a[0].date) || b.length - a.length).slice(0, 8);
    $("#feed").innerHTML = feed.map((g) => {
      const lines = ["FC", "NL", "1D"].map((t) => {
        const rs = g.filter((r) => r.topology === t);
        if (!rs.length) return "";
        const ns = rs.map((r) => r.nq), lo = Math.min(...ns), hi = Math.max(...ns);
        const pass = rs.filter((r) => r.passes), size = lo === hi ? `${lo} qubits` : `${lo}–${hi} qubits`;
        const st = pass.length ? (lo === hi ? `<span class="st ok">✓ above random</span>` : `<span class="st ok">✓ above random up to ${Math.max(...pass.map((r) => r.nq))} q</span>`)
          : rs.some((r) => r.passes === false) ? `<span class="st no">✗ not above random</span>` : `<span class="st na">– no random baseline</span>`;
        const best = rs.length === 1 ? ` · best r ${f3(rs[0].best.r)}` : ` · ${rs.length} sizes`;
        return `<span class="m">${TOPO[t]} · ${size}${best}</span>${st}`;
      }).join("");
      return `<li><span class="d">${fDate(g[0].date)}</span><span class="n">${esc(dev(g[0]).name)}</span>${lines}</li>`;
    }).join("");

    /* pending */
    if (data.pending.length) $("#pending").innerHTML = data.pending.map((p) => `<li><code>${esc(p.file.replace(/^Data\//, ""))}</code></li>`).join("");

    renderFC(); renderCurves("nl", RUNS.filter((r) => r.topology === "NL" && isQpu(r)));
    renderChain();

    /* ---------- fully connected ---------- */
    function renderFC() {
      const emuBox = $("#fcEmu");
      const picker = Picker(() => { drawChart(); });
      let drawChart = () => {};
      const update = () => {
        const fc = RUNS.filter((r) => r.topology === "FC" && (isQpu(r) || (emuBox.checked && dev(r).kind === "emulator")));
        const byDev = {};
        fc.forEach((r) => (byDev[r.device] = byDev[r.device] || []).push(r));
        const rows = Object.entries(byDev).map(([d, rs]) => {
          const pass = rs.filter((r) => r.passes).sort((a, b) => b.nq - a.nq)[0];
          return { d, rs, pass, n: pass ? pass.nq : 0 };
        }).sort((a, b) => b.n - a.n || DEV[a.d].name.localeCompare(DEV[b.d].name));
        const maxN = Math.max(...rows.map((r) => r.n), 1);

        /* leaderboard */
        const lb = $("#lb"); lb.innerHTML = "";
        rows.forEach((row) => {
          const meta = DEV[row.d], col = meta.modality === "trapped ion" ? "var(--ion)" : "var(--sc)";
          const div = document.createElement("div");
          div.className = "lb-row"; div.setAttribute("role", "listitem");
          div.innerHTML = `<span class="lb-name">${esc(meta.name)}</span><span class="lb-track">${row.n ? `<span class="lb-bar" style="width:${(row.n / maxN) * 82}%;background:${col}"></span>` : ""}<span class="lb-val">${row.n ? row.n + " qubits" : "none above random"}</span></span>`;
          const r = row.pass;
          const html = `<b>${esc(meta.name)}</b>${meta.kind !== "qpu" ? " (emulator)" : ""}<br>` + (r
            ? `<span class="k">Largest N above random:</span> ${r.nq}<br><span class="k">Best r:</span> ${f3(r.best.r)} at p = ${r.best.p}<br><span class="k">r<sub>eff</sub>:</span> ${f3(r.r_eff)}${gatesTip(r, r.best.p)}<br><span class="k">Shots:</span> ${fInt(r.shots)} · ${fDate(r.date)}`
            : `No size above random. Sizes tried: ${row.rs.map((x) => x.nq).sort((a, b) => a - b).join(", ")}`);
          div.addEventListener("pointermove", (ev) => showTip(html, ev.clientX, ev.clientY));
          div.addEventListener("pointerleave", hideTip);
          lb.appendChild(div);
        });
        $("#lbLegend").innerHTML = `<span><i class="dot" style="background:var(--sc)"></i>superconducting</span><span><i class="dot" style="background:var(--ion)"></i>trapped ion</span>`;

        /* r_eff vs N */
        if (!picker.keys().length) picker.set(rows.filter((r) => r.n).slice(0, 3).map((r) => r.d));
        picker.keepOnly((k) => !!byDev[k]);
        drawChart = () => {
          const series = Object.entries(byDev).map(([d, rs]) => ({
            key: d, label: DEV[d].name, color: picker.color(d),
            pts: rs.filter((r) => r.r_eff != null).map((r) => ({ x: r.nq, y: r.r_eff, hollow: !r.passes, run: r })),
          }));
          renderChips($("#fcChips"), rows.map((r) => ({ key: r.d, label: DEV[r.d].name })), picker);
          renderLegend($("#fcLegend"), picker, (k) => DEV[k].name,
            `<span><i class="dot" style="background:var(--muted)"></i>above random</span><span><i class="hollow"></i>not above random</span>`);
          const host = $("#fcChart");
          const fn = () => lineChart(host, {
            series, xLabel: "Problem size N (qubits)", yLabel: "Effective approximation ratio r_eff",
            refs: [{ y: 0, label: "random + 3σ" }], aria: "Effective approximation ratio versus number of qubits, fully connected graphs",
            onPick: (k) => picker.toggle(k),
            tip: (s, p) => `<b>${esc(s.label)}</b> · N = ${p.x}<br><span class="k">r<sub>eff</sub>:</span> ${f3(p.y)} · ${status(p.run)}<br><span class="k">Best r:</span> ${f3(p.run.best.r)} at p = ${p.run.best.p}${gatesTip(p.run, p.run.best.p)}<br><span class="k">Shots:</span> ${fInt(p.run.shots)} · ${fDate(p.run.date)}`,
          });
          fn(); host._redraw = fn;
        };
        drawChart();
      };
      emuBox.addEventListener("change", update);
      update();
      autoRedraw($("#fcChart"), () => $("#fcChart")._redraw && $("#fcChart")._redraw());
    }

    /* ---------- r vs p curves (native layout, 1D chain) ---------- */
    function renderCurves(prefix, runs, keepPicker) {
      const picker = keepPicker || Picker(() => draw());
      const byId = Object.fromEntries(runs.map((r) => [r.id, r]));
      picker.keepOnly((k) => !!byId[k]);
      if (!picker.keys().length) picker.set([...runs].sort((a, b) => b.best.r - a.best.r).slice(0, 3).map((r) => r.id));
      const items = [...runs].sort((a, b) => runLabel(a).localeCompare(runLabel(b))).map((r) => ({ key: r.id, label: runLabel(r) + (prefix === "nl" ? ` · ${r.nq} q` : "") }));
      const host = $(`#${prefix}Chart`);
      function draw() {
        renderChips($(`#${prefix}Chips`), items, picker);
        renderLegend($(`#${prefix}Legend`), picker, (k) => runLabel(byId[k]));
        const first = byId[picker.keys().sort((a, b) => SLOTS.indexOf(picker.color(a)) - SLOTS.indexOf(picker.color(b)))[0]];
        const series = runs.map((r) => ({
          key: r.id, label: runLabel(r), color: picker.color(r.id),
          pts: r.p.map((p, i) => ({ x: Math.max(p, 1), y: r.r[i], run: r })),
        }));
        const fn = () => lineChart(host, {
          series, xLog: true, xLabel: "LR-QAOA layers p", yLabel: "Approximation ratio r",
          refs: first && first.random ? [{ y: first.random.threshold, label: `random + 3σ (${runLabel(first)})` }] : [],
          aria: `Approximation ratio versus layers, ${TOPO[runs[0] ? runs[0].topology : "NL"]}`,
          onPick: (k) => picker.toggle(k),
          tip: (s, pt) => `<b>${esc(s.label)}</b> · ${pt.run.nq} qubits<br><span class="k">p =</span> ${fInt(pt.x)} · <span class="k">r =</span> ${f3(pt.y)}${pt.run.random ? `<br><span class="k">random + 3σ:</span> ${f3(pt.run.random.threshold)} ${pt.y > pt.run.random.threshold ? '<span class="st ok">✓ above</span>' : '<span class="st no">✗ below</span>'}` : ""}${gatesTip(pt.run, pt.x)}<br><span class="k">Added</span> ${fDate(pt.run.date)}`,
        });
        fn(); host._redraw = fn;
        renderTable(prefix, runs, picker);
      }
      if (!host._observed) { autoRedraw(host, () => host._redraw && host._redraw()); host._observed = true; }
      draw();
      return picker;
    }

    function renderTable(prefix, runs, picker) {
      const rows = [...runs].sort((a, b) => b.best.r - a.best.r);
      $(`#${prefix}Table`).innerHTML = `<thead><tr><th>Device</th><th>Qubits</th><th>Best r</th><th>at p</th><th>Deepest p above random</th><th>2-qubit gates there</th><th>Shots</th><th>Added</th></tr></thead><tbody>`
        + rows.map((r) => `<tr class="${picker.has(r.id) ? "sel" : ""}" data-k="${esc(r.id)}"><td>${picker.has(r.id) ? `<i style="display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;background:${picker.color(r.id)}"></i>` : ""}${esc(runLabel(r))}</td><td>${r.nq}</td><td>${f3(r.best.r)}</td><td>${fInt(r.best.p)}</td><td>${r.random ? (r.deepest_p_above_random ? fInt(r.deepest_p_above_random) : "none") : "–"}</td><td>${fInt(r.gates_at_deepest)}</td><td>${fInt(r.shots)}</td><td>${fDate(r.date)}</td></tr>`).join("") + "</tbody>";
      $(`#${prefix}Table`).querySelectorAll("tbody tr").forEach((tr) => { tr.style.cursor = "pointer"; tr.addEventListener("click", () => picker.toggle(tr.dataset.k)); });
    }

    /* ---------- 1D chain: one chart per chain length ---------- */
    function renderChain() {
      const chain = RUNS.filter((r) => r.topology === "1D" && isQpu(r));
      const counts = {};
      chain.forEach((r) => (counts[r.nq] = (counts[r.nq] || 0) + 1));
      const sizes = Object.keys(counts).map(Number).filter((n) => counts[n] >= 2 || n >= 50).sort((a, b) => a - b);
      let size = sizes.includes(100) ? 100 : sizes[sizes.length - 1];
      const seg = $("#chainSize");
      const pickers = {};
      const show = () => {
        seg.innerHTML = sizes.map((n) => `<button type="button" role="tab" aria-selected="${n === size}" data-n="${n}">${n} qubits</button>`).join("");
        seg.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { size = +b.dataset.n; show(); }));
        pickers[size] = renderCurves("chain", chain.filter((r) => r.nq === size), pickers[size]);
      };
      show();
    }
  }

  /* ---------- cite ---------- */
  $("#copyCite").addEventListener("click", (ev) => {
    const txt = $("#cite pre").innerText;
    (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(
      () => { ev.target.textContent = "Copied"; setTimeout(() => (ev.target.textContent = "Copy BibTeX"), 1500); },
      () => {});
  });
})();
