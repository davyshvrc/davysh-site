(() => {
  if (!('IntersectionObserver' in window) || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const els = document.querySelectorAll('.drop, .drop-month-title, .sec-head, .worlds-head, .card, .world, .line, .framed, .about-head, .about-body, .about-facts, .cartel-join, .teaser-panel, .tier, .right-card, .step, .find-list li, .foot-mark, .foot .divider');
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
  const vh = innerHeight;
  els.forEach((el) => { if (el.getBoundingClientRect().top > vh) { el.classList.add('rv'); io.observe(el); } });
})();

/* v3.9 scroll-spy: the nav marks the section being read. Not motion, so it also
   runs with reduced motion; it only needs IntersectionObserver. */
(() => {
  if (!('IntersectionObserver' in window)) return;
  const links = new Map();
  document.querySelectorAll('.pill-links a[href^="#"]').forEach((a) => links.set(a.getAttribute('href').slice(1), a));
  if (!links.size) return;
  const spy = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      links.forEach((a) => a.removeAttribute('aria-current'));
      const here = links.get(e.target.id);
      if (here) here.setAttribute('aria-current', 'true');
    }
  }, { rootMargin: '-42% 0px -55% 0px' });
  document.querySelectorAll('main > section[id]').forEach((sec) => spy.observe(sec));
})();
