/* Product pages: a slim buy bar slides up on small screens once the main buy panel has scrolled away. */
(() => {
  const buy = document.querySelector('.pd-buy'), bar = document.querySelector('.pd-bar');
  if (!buy || !bar || !('IntersectionObserver' in window)) return;
  new IntersectionObserver(([e]) => {
    const on = !e.isIntersecting && e.boundingClientRect.top < 0;
    bar.classList.toggle('on', on);
    bar.inert = !on;
  }).observe(buy);
  bar.inert = true;
})();
