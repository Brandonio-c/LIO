/* Food-profile Explore drawing (owner 2026-11-25: readable axes, labels, legend). */
(function (global) {
  function css(name, fallback) {
    const v = getComputedStyle(document.body).getPropertyValue(name).trim();
    return v || fallback;
  }
  function fit(canvas) {
    // Draw at the displayed size (sharp text on retina screens).
    const dpr = global.devicePixelRatio || 1;
    const w = Math.max(320, canvas.clientWidth || canvas.width);
    const h = Math.max(220, canvas.clientHeight || canvas.height);
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.font = "12px system-ui, -apple-system, sans-serif";
    return { ctx, W: w, H: h };
  }
  function hex(c) {
    const m = /^#?([0-9a-f]{6})$/i.exec(c.trim());
    if (!m) return [42, 120, 214];
    const n = parseInt(m[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function mix(a, b, t) {
    return `rgb(${a.map((x, i) => Math.round(x + (b[i] - x) * t)).join(",")})`;
  }
  function niceTicks(lo, hi, n) {
    const span = hi - lo || 1;
    const step0 = Math.pow(10, Math.floor(Math.log10(span / n)));
    const step = [1, 2, 5, 10].map((k) => k * step0).find((s) => span / s <= n) || step0 * 10;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
    return out;
  }
  function mmOf(payloadOrNull, hs, mmPerHs) {
    return mmPerHs ? hs * mmPerHs : hs;
  }

  // Hole x height grid. opts: {mmPerHs, onPickHole, selectedHole}
  function drawHeatmap(canvas, payload, opts) {
    opts = opts || {};
    const { ctx, W, H } = fit(canvas);
    const ink = css("--ink", "#e8e8e8"), muted = css("--muted", "#9a9a9a");
    const lo = hex(css("--surface-2", "#262626")), hi = hex(css("--accent", "#3b82f6"));
    if (!payload || !payload.heights_hs || !payload.heights_hs.length) {
      ctx.fillStyle = muted; ctx.fillText("no height data in this run (stationary or empty)", 12, 20); return;
    }
    const L = 118, R = 70, T = 8, B = 36;
    const heights = payload.heights_hs, nh = heights.length;
    const holes = payload.holes || [...Array(16).keys()].map((i) => i + 1);
    const cw = (W - L - R) / nh, ch = (H - T - B) / holes.length;
    let mx = 0;
    payload.net.forEach((row) => row.forEach((v) => { if (v != null && v > mx) mx = v; }));
    if (mx <= 0) mx = 1;
    const chans = payload.channels || {};
    holes.forEach((hole, r) => {
      const c = chans[String(hole)] || {};
      const blind = (payload.reasons[r] || []).every((x) => x === "blind");
      // row label: hole + wavelength/label
      ctx.fillStyle = blind ? muted : ink;
      ctx.textAlign = "right"; ctx.textBaseline = "middle";
      const lab = `h${hole} ${c.wavelength_nm ? Math.round(c.wavelength_nm) + " nm" : ""}${c.broadband ? " (" + (c.label || "") + ")" : ""}`;
      ctx.fillText(lab, L - 6, T + r * ch + ch / 2);
      for (let i = 0; i < nh; i++) {
        const v = payload.net[r][i], reason = (payload.reasons[r] || [])[i];
        if (reason === "blind") ctx.fillStyle = mix(lo, lo, 0);
        else if (v == null) ctx.fillStyle = mix(lo, lo, 0);
        else ctx.fillStyle = mix(lo, hi, Math.max(0, Math.min(1, v / mx)));
        ctx.fillRect(L + i * cw, T + r * ch, Math.max(1, cw - 1), Math.max(1, ch - 1));
        if (reason === "blind" && i === 0) {
          ctx.fillStyle = muted; ctx.textAlign = "left";
          ctx.fillText("not seen by this detector", L + 6, T + r * ch + ch / 2);
        }
      }
      if (opts.selectedHole === hole) {
        ctx.strokeStyle = ink; ctx.lineWidth = 2;
        ctx.strokeRect(L - 1, T + r * ch, W - L - R + 2, ch - 1);
      }
    });
    // x axis: height (mm below the top, or half-steps)
    ctx.fillStyle = muted; ctx.textAlign = "center"; ctx.textBaseline = "top";
    const xs = heights.map((h) => mmOf(payload, h, opts.mmPerHs));
    const ticks = niceTicks(Math.min(...xs), Math.max(...xs), 6);
    ticks.forEach((t) => {
      const i = xs.reduce((best, x, k) => (Math.abs(x - t) < Math.abs(xs[best] - t) ? k : best), 0);
      ctx.fillText(opts.mmPerHs ? `${t}` : `${Math.round(t / 1000)}k`, L + i * cw + cw / 2, H - B + 4);
    });
    ctx.fillText(opts.mmPerHs ? "head height (mm from the top)" : "head height (half-steps)", L + (W - L - R) / 2, H - 16);
    // legend
    const lx = W - R + 18, ly = T, lh = H - T - B;
    for (let k = 0; k < lh; k++) { ctx.fillStyle = mix(lo, hi, 1 - k / lh); ctx.fillRect(lx, ly + k, 12, 1); }
    ctx.fillStyle = muted; ctx.textAlign = "left"; ctx.textBaseline = "middle";
    ctx.fillText(`${Math.round(mx)}`, lx + 16, ly + 6);
    ctx.fillText("0", lx + 16, ly + lh - 6);
    ctx.save(); ctx.translate(lx + 46, ly + lh / 2); ctx.rotate(-Math.PI / 2); ctx.textAlign = "center";
    ctx.fillText("net counts", 0, 0); ctx.restore();
    canvas.onclick = (e) => {
      if (!opts.onPickHole) return;
      const rect = canvas.getBoundingClientRect();
      const r = Math.floor((e.clientY - rect.top - T) / ch);
      if (r >= 0 && r < holes.length) opts.onPickHole(holes[r]);
    };
    canvas.style.cursor = opts.onPickHole ? "pointer" : "";
  }

  // One hole's net vs height: every reading as a dot, the mean per height as a line.
  function drawCurve(canvas, payload, opts) {
    opts = opts || {};
    const { ctx, W, H } = fit(canvas);
    const ink = css("--ink", "#e8e8e8"), muted = css("--muted", "#9a9a9a"), hair = css("--hair", "#333");
    const accent = css("--accent", "#3b82f6");
    const pts = (payload && payload.points) || [];
    if (!pts.length) {
      ctx.fillStyle = muted;
      ctx.fillText(payload && payload.reason === "blind" ? "this detector cannot see this hole" : "no readings for this hole", 12, 20);
      return;
    }
    const L = 56, R = 12, T = 22, B = 36;
    const x = (p) => mmOf(payload, p.height_hs, opts.mmPerHs);
    const xs = pts.map(x), ys = pts.map((p) => p.net_counts);
    const xmin = Math.min(...xs), xmax = Math.max(...xs);
    const ymin = Math.min(0, ...ys), ymax = Math.max(...ys, 1);
    const sx = (v) => L + (W - L - R) * ((v - xmin) / ((xmax - xmin) || 1));
    const sy = (v) => H - B - (H - T - B) * ((v - ymin) / ((ymax - ymin) || 1));
    // grid + y ticks
    ctx.strokeStyle = hair; ctx.lineWidth = 1; ctx.fillStyle = muted; ctx.textAlign = "right"; ctx.textBaseline = "middle";
    niceTicks(ymin, ymax, 5).forEach((t) => {
      ctx.beginPath(); ctx.moveTo(L, sy(t)); ctx.lineTo(W - R, sy(t)); ctx.stroke();
      ctx.fillText(String(t), L - 6, sy(t));
    });
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    niceTicks(xmin, xmax, 6).forEach((t) => ctx.fillText(String(t), sx(t), H - B + 4));
    ctx.fillText(opts.mmPerHs ? "head height (mm from the top)" : "head height (half-steps)", L + (W - L - R) / 2, H - 16);
    ctx.save(); ctx.translate(14, T + (H - T - B) / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText("net counts (lit − dark)", 0, 0); ctx.restore();
    // readings
    ctx.fillStyle = muted;
    pts.forEach((p) => { ctx.beginPath(); ctx.arc(sx(x(p)), sy(p.net_counts), 2.5, 0, 2 * Math.PI); ctx.fill(); });
    // mean per height
    const by = new Map();
    pts.forEach((p) => { const k = x(p); (by.get(k) || by.set(k, []).get(k)).push(p.net_counts); });
    const mean = [...by.entries()].sort((a, b) => a[0] - b[0]).map(([k, v]) => [k, v.reduce((s, y) => s + y, 0) / v.length]);
    ctx.strokeStyle = accent; ctx.lineWidth = 2; ctx.beginPath();
    mean.forEach(([k, v], i) => (i ? ctx.lineTo(sx(k), sy(v)) : ctx.moveTo(sx(k), sy(v))));
    ctx.stroke();
    // title
    ctx.fillStyle = ink; ctx.textAlign = "left"; ctx.textBaseline = "top";
    ctx.fillText(opts.title || `hole ${payload.hole}`, L, 4);
    ctx.fillStyle = muted; ctx.textAlign = "right";
    ctx.fillText("dots: each reading · line: mean per height", W - R, 4);
  }
  global.LIOProfiles = { drawHeatmap, drawCurve };
})(typeof window !== "undefined" ? window : globalThis);
