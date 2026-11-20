/* Food-profile Explore UI helpers (loaded optionally; also inlined below in index). */
(function (global) {
  function drawHeatmap(canvas, payload) {
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);
    if (!payload || !payload.heights_hs || !payload.heights_hs.length) {
      ctx.fillStyle = "#888"; ctx.fillText("no data", 12, 20); return;
    }
    const nets = payload.net;
    let mx = 0;
    for (const row of nets) for (const v of row) if (v != null && Math.abs(v) > mx) mx = Math.abs(v);
    if (mx <= 0) mx = 1;
    const nh = payload.heights_hs.length, nw = 16;
    const cw = W / nh, ch = H / nw;
    for (let hole = 0; hole < 16; hole++) {
      for (let hi = 0; hi < nh; hi++) {
        const v = nets[hole][hi];
        const reason = (payload.reasons && payload.reasons[hole][hi]) || "";
        if (reason === "blind") ctx.fillStyle = "#c8c8c8";
        else if (v == null) ctx.fillStyle = "#eee";
        else {
          const t = Math.min(1, Math.abs(v) / mx);
          ctx.fillStyle = `rgba(42,120,214,${0.15 + 0.85 * t})`;
        }
        ctx.fillRect(hi * cw, hole * ch, cw + 0.5, ch + 0.5);
      }
    }
  }
  function drawCurve(canvas, payload) {
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);
    const pts = (payload && payload.points) || [];
    if (!pts.length) { ctx.fillStyle = "#888"; ctx.fillText(payload && payload.reason || "no points", 12, 20); return; }
    const xs = pts.map(p => p.height_hs), ys = pts.map(p => p.net_counts);
    const xmin = Math.min(...xs), xmax = Math.max(...xs);
    const ymin = Math.min(...ys), ymax = Math.max(...ys);
    const xspan = (xmax - xmin) || 1, yspan = (ymax - ymin) || 1;
    ctx.strokeStyle = "#2a78d6"; ctx.beginPath();
    pts.forEach((p, i) => {
      const x = 20 + (W - 40) * ((p.height_hs - xmin) / xspan);
      const y = H - 20 - (H - 40) * ((p.net_counts - ymin) / yspan);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }
  global.LIOProfiles = { drawHeatmap, drawCurve };
})(typeof window !== "undefined" ? window : globalThis);
