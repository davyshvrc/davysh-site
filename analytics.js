/* Privacy-friendly analytics (GoatCounter): no cookies, no personal data.
   Site code: davysh (https://davysh.goatcounter.com). Not loaded on localhost or file://.
   Click events: any element with data-goatcounter-click="event-name" is counted. */
(function () {
  var code = 'davysh';
  if (/^(localhost|127\.|0\.0\.0\.0|\[::1\])/.test(location.hostname) || location.protocol === 'file:') return;
  var s = document.createElement('script');
  s.async = true;
  s.src = 'https://gc.zgo.at/count.js';
  s.setAttribute('data-goatcounter', 'https://' + code + '.goatcounter.com/count');
  document.head.appendChild(s);
})();
