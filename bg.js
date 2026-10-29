/* Liquid chrome background: tiny canvas, smooth domain-warped sine field.
   ~24 fps, pauses when the tab is hidden; one still frame with reduced motion. */
(function () {
  var sky = document.querySelector('.sky');
  if (!sky || !window.requestAnimationFrame) return;
  var c = document.createElement('canvas'), g = c.getContext('2d');
  if (!g) return;
  sky.appendChild(c);
  var still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var W, H, img, t0 = performance.now(), last = 0, raf = 0;
  function size() {
    var a = innerHeight / Math.max(1, innerWidth);
    W = innerWidth < 700 ? 120 : 200; H = Math.max(60, Math.round(W * a));
    c.width = W; c.height = H; img = g.createImageData(W, H);
  }
  function frame(t) {
    var s = (t - t0) / 1000 * 0.045, d = img.data, i = 0;
    for (var y = 0; y < H; y++) {
      var v = y / W;
      for (var x = 0; x < W; x++) {
        var u = x / W;
        var wx = u + 0.42 * Math.sin(v * 3.6 + s * 1.3) + 0.2 * Math.sin(u * 6.1 - s);
        var wy = v + 0.30 * Math.cos(u * 2.7 - s * 1.1) + 0.15 * Math.sin(v * 4.6 + s * 0.7);
        var f = Math.sin(wx * 9.5 + wy * 4.2 + s * 2.0) * 0.5 + Math.sin(wy * 11.0 - wx * 3.3 - s * 1.4) * 0.5;
        var band = Math.pow(1 - Math.min(1, Math.abs(f)), 9);      /* thin bright ridges = chrome caustics */
        var body = (f * 0.5 + 0.5) * 0.35;                          /* soft silk body */
        var k = 0.7 * band + 0.3 * body;
        k *= 0.55 + 0.45 * Math.min(1, u * 1.6);                    /* calmer behind the hero copy */
        var dx = u - 0.08, dy = v - 0.95 * H / W;
        var wine = Math.max(0, 1 - (dx * dx + dy * dy) * 2.6) * (0.55 + 0.45 * body); /* wine pool, lower left */
        var r = 7 + k * 46 + wine * 40, gg = 7 + k * 46 + wine * 6, b = 8 + k * 52 + wine * 12;
        d[i++] = r; d[i++] = gg; d[i++] = b; d[i++] = 255;
      }
    }
    g.putImageData(img, 0, 0);
  }
  function loop(t) {
    raf = requestAnimationFrame(loop);
    if (t - last < 42) return;
    last = t; frame(t);
  }
  size(); frame(t0); c.className = 'on';
  addEventListener('resize', function () { size(); frame(performance.now()); });
  if (still) return;
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) cancelAnimationFrame(raf); else raf = requestAnimationFrame(loop);
  });
  raf = requestAnimationFrame(loop);
})();
