/* Liquid chrome background, v3.8.
   Ridges are drawn as real vector strokes on a canvas backed at the screen's
   own pixel density (up to 2x, capped near 4K pixel count), so they stay sharp
   on retina and 4K displays. Each ridge: soft halo + thin specular core.
   The black silk and the wine pool are plain CSS gradients underneath.
   Starts only after the page has loaded and the main thread is idle, so it
   never competes with the hero image.
   ~20 fps, pauses when the tab is hidden; one still frame with reduced motion. */
function dvChrome() {
  var sky = document.querySelector('.sky');
  if (!sky || !window.requestAnimationFrame) return;
  var c = document.createElement('canvas'), g = c.getContext('2d');
  if (!g) return;
  sky.appendChild(c);
  var still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var MAX_PX = 3840 * 2160;                 /* never allocate more than a 4K frame */
  var W = 0, H = 0, R = 1, t0 = performance.now(), last = 0, raf = 0;

  /* [axis, base, amp1, freq1, speed1, amp2, freq2, speed2, phase, strength]
     axis 0 = flows left-right, 1 = flows top-bottom (gives the woven caustic) */
  var RIDGES = [
    [0, .20, .13, 1.30, .50, .05, 2.9, -.33, 0.0, 1.00],
    [0, .52, .15, 1.10, -.42, .05, 2.6, .27, 1.7, .85],
    [0, .84, .11, 1.45, .36, .04, 3.3, -.21, 3.1, .75],
    [1, .12, .10, 1.20, .40, .05, 2.7, -.30, 0.9, .80],
    [1, .55, .13, 1.05, -.34, .05, 2.4, .24, 2.4, 1.00],
    [1, .86, .11, 1.35, .28, .04, 3.0, -.40, 5.2, .85]
  ];

  var GLOW = [[16, '186,192,206', 0.016], [8, '200,205,216', 0.024], [3.5, '218,222,232', 0.05]];

  function size() {
    W = sky.clientWidth || innerWidth; H = sky.clientHeight || innerHeight;
    R = Math.min(window.devicePixelRatio || 1, 2);   /* 2x is already crisp; 3x costs 2.25x the fill */
    if (W * H * R * R > MAX_PX) R = Math.sqrt(MAX_PX / (W * H));
    c.width = Math.round(W * R); c.height = Math.round(H * R);
  }

  function path(g, r, s) {
    var ax = r[0], L = ax ? H : W, S = ax ? W : H, n = Math.max(24, Math.round(L / 22)), px, py, i, u, o, x, y;
    g.beginPath();
    for (i = 0; i <= n; i++) {
      u = -0.08 + 1.16 * i / n;
      o = r[1] + r[2] * Math.sin(u * r[3] * Math.PI + s * r[4] + r[8])
               + r[5] * Math.sin(u * r[6] * Math.PI + s * r[7] + r[8] * 1.7);
      x = ax ? o * S : u * L; y = ax ? u * L : o * S;
      if (!i) g.moveTo(x, y);
      else g.quadraticCurveTo(px, py, (px + x) / 2, (py + y) / 2);   /* smooth through midpoints */
      px = x; py = y;
    }
    g.lineTo(px, py);
  }

  /* calmer behind the hero copy on the left (folded into the stroke colours,
     so there is no full-screen mask or blur to recomposite every frame) */
  function fade(x) { var q = Math.min(1, Math.max(0, (x - 0.28) / 0.36)); return 0.42 + 0.58 * q * q * (3 - 2 * q); }
  function spec(u, p) { var d = Math.abs(u - p); d = Math.min(d, 1 - d); return 0.30 + 0.50 * Math.max(0, 1 - d / 0.18); }

  function hgrad(x, rgb, al, a) {               /* horizontal fade gradient for a ridge pass */
    var gr = x.createLinearGradient(0, 0, W, 0), j;
    for (j = 0; j <= 4; j++) gr.addColorStop(j / 4, 'rgba(' + rgb + ',' + (al * a * fade(j / 4)) + ')');
    return gr;
  }

  function frame(t) {
    var s = Math.max(0, t - t0) / 1000 * 0.11, k, r, a, grad, p, j, u, f, hz, N = 20;
    g.setTransform(R, 0, 0, R, 0, 0);
    g.clearRect(0, 0, W, H);
    g.lineCap = 'round'; g.lineJoin = 'round'; g.globalCompositeOperation = 'lighter';
    for (k = 0; k < RIDGES.length; k++) {
      r = RIDGES[k]; hz = !r[0]; a = r[9] * (hz ? 1 : fade(r[1]));
      p = ((s * 0.18 + k * 0.29) % 1 + 1) % 1;                       /* a highlight travels along the ridge */
      path(g, r, s);
      for (j = 0; j < 3; j++) {                                       /* soft falloff: 3 graded passes */
        g.strokeStyle = hz ? hgrad(g, GLOW[j][1], GLOW[j][2], a) : 'rgba(' + GLOW[j][1] + ',' + (GLOW[j][2] * a) + ')';
        g.lineWidth = GLOW[j][0]; g.stroke();
      }
      grad = hz ? g.createLinearGradient(0, 0, W, 0) : g.createLinearGradient(0, 0, 0, H);
      for (j = 0; j <= N; j++) {
        u = j / N; f = (spec(u, p) - .3) / .5;                       /* 0 = chrome, 1 = specular white */
        grad.addColorStop(u, 'rgba(' + Math.round(200 + 46 * f) + ',' + Math.round(204 + 44 * f) + ',' + Math.round(212 + 39 * f) + ',' +
          (spec(u, p) * a * (hz ? fade(u) : 1)).toFixed(3) + ')');
      }
      g.strokeStyle = grad;
      g.lineWidth = R >= 2 ? 0.9 : 1.1;                              /* specular core: ~2 device px, crisp edges */
      g.stroke();
    }
    g.globalCompositeOperation = 'source-over';
  }

  /* if the device is struggling (many late rAF ticks), ease off to ~12 fps */
  var step = 50, prev = 0, ticks = 0, late = 0;
  function loop(t) {
    raf = requestAnimationFrame(loop);
    if (prev && ticks < 120) { ticks++; if (t - prev > 25) late++; if (ticks === 120 && late > 36) step = 83; }
    prev = t;
    if (t - last < step) return;               /* ~20 fps: the flow moves ~5 px/s, so this is still smooth */
    last = t; frame(t);
  }
  var rt = 0;
  size(); frame(t0); c.className = 'on';
  addEventListener('resize', function () {
    clearTimeout(rt);
    rt = setTimeout(function () { size(); frame(performance.now()); }, 120);
  });
  if (/^(localhost|127\.0\.0\.1)$/.test(location.hostname)) window.__dvChrome = {   /* local perf probe only */
     frame: frame, info: function () { return { cw: c.width, ch: c.height, dpr: R }; } };
  if (still) return;
  document.addEventListener('visibilitychange', function () {
    cancelAnimationFrame(raf);
    prev = 0;
    if (!document.hidden) raf = requestAnimationFrame(loop);
  });
  raf = requestAnimationFrame(loop);
}
(function () {
  function idle() { (window.requestIdleCallback || function (f) { setTimeout(f, 200); })(dvChrome, { timeout: 1500 }); }
  if (document.readyState === 'complete') idle(); else addEventListener('load', idle, { once: true });
})();
