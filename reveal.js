(() => {
  if (!('IntersectionObserver' in window) || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const els = document.querySelectorAll('.drop, .drop-month-title, .sec-head, .worlds-head, .card, .world, .line, .framed, .about-head, .about-body, .about-facts, .cartel-join, .teaser-panel, .tier, .right-card, .step, .find-list li, .foot-mark, .foot .divider');
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
  const vh = innerHeight;
  els.forEach((el) => { if (el.getBoundingClientRect().top > vh) { el.classList.add('rv'); io.observe(el); } });
})();
