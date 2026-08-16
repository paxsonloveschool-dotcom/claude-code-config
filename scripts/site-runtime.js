/* HP Landscaping — vanilla replacement for the Webflow IX2 runtime.
 * Zero dependencies. Replaces: mobile nav, scroll reveals, stat counters,
 * dark-mode toggle, background-video kick. Progressive enhancement only —
 * every page is fully readable with this file absent.
 */
(function () {
  'use strict';
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Reveal-on-scroll. Build step stripped the inline opacity:0 and tagged
     targets with [data-reveal]; styling lives in an injected scoped rule so
     it never fights the design system CSS. */
  function reveals() {
    var nodes = document.querySelectorAll('[data-reveal]');
    if (!nodes.length) return;
    if (reduce || !('IntersectionObserver' in window)) {
      nodes.forEach(function (n) { n.classList.add('is-revealed'); });
      return;
    }
    var s = document.createElement('style');
    s.textContent =
      '[data-reveal]{opacity:0;transform:translateY(24px);' +
      'transition:opacity .7s ease,transform .7s ease}' +
      '[data-reveal].is-revealed{opacity:1;transform:none}';
    document.head.appendChild(s);
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('is-revealed'); io.unobserve(e.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    nodes.forEach(function (n) { io.observe(n); });
  }

  /* Mobile nav — drives the exact classes/attrs components.css already styles
     (w--open on the button, [data-nav-menu-open] on the menu). */
  function nav() {
    var btn = document.querySelector('.cf-nav-5-menu-button-4');
    var menu = document.querySelector('.cf-nav-menu-4');
    if (!btn || !menu) return;
    btn.setAttribute('role', 'button');
    btn.setAttribute('tabindex', '0');
    btn.setAttribute('aria-label', 'Menu');
    btn.setAttribute('aria-expanded', 'false');
    function toggle(open) {
      var isOpen = open != null ? open : !btn.classList.contains('w--open');
      btn.classList.toggle('w--open', isOpen);
      btn.setAttribute('aria-expanded', String(isOpen));
      if (isOpen) menu.setAttribute('data-nav-menu-open', '');
      else menu.removeAttribute('data-nav-menu-open');
    }
    btn.addEventListener('click', function () { toggle(); });
    btn.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
    });
    menu.addEventListener('click', function (e) {
      if (e.target.closest('a')) toggle(false);
    });
    window.addEventListener('resize', function () {
      if (window.innerWidth > 991) toggle(false);
    });
  }

  /* Stat counters — mirrors the old jquery.counterUp on .span-quarter-river. */
  function counters() {
    var els = document.querySelectorAll('.span-quarter-river');
    if (!els.length || !('IntersectionObserver' in window)) return;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        io.unobserve(e.target);
        run(e.target);
      });
    }, { threshold: 0.5 });
    els.forEach(function (el) { io.observe(el); });

    function run(el) {
      var raw = el.textContent.trim();
      var m = raw.match(/([\d,.]+)/);
      if (!m) return;
      var target = parseFloat(m[1].replace(/,/g, ''));
      if (isNaN(target)) return;
      var prefix = raw.slice(0, m.index);
      var suffix = raw.slice(m.index + m[1].length);
      var hasComma = m[1].indexOf(',') > -1;
      if (reduce) return;
      var dur = 1500, start = null;
      function fmt(n) {
        n = Math.floor(n);
        return hasComma ? n.toLocaleString('en-US') : String(n);
      }
      function step(ts) {
        if (start == null) start = ts;
        var p = Math.min((ts - start) / dur, 1);
        el.textContent = prefix + fmt(target * p) + suffix;
        if (p < 1) requestAnimationFrame(step);
        else el.textContent = raw;
      }
      el.textContent = prefix + '0' + suffix;
      requestAnimationFrame(step);
    }
  }

  /* Dark-mode toggle — replaces the Lottie .darkify control. Preference
     persists; the conservative dark skin lives under html.theme-dark. */
  function darkMode() {
    var KEY = 'hp-theme';
    var root = document.documentElement;
    try {
      if (localStorage.getItem(KEY) === 'dark') root.classList.add('theme-dark');
    } catch (e) {}
    if (!document.getElementById('hp-dark-skin')) {
      var s = document.createElement('style');
      s.id = 'hp-dark-skin';
      s.textContent =
        'html.theme-dark .body,html.theme-dark body{background:#0a1511;color:#e7efe9}' +
        'html.theme-dark .about-us,html.theme-dark .about-us.auu{background:#0d1a14}' +
        'html.theme-dark .cf-nav-4.subpages{background:transparent}' +
        'html.theme-dark .darkify .toggle{background:#2fba54}';
      document.head.appendChild(s);
    }
    var btn = document.querySelector('.darkify .toggle');
    if (!btn) return;
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      var on = root.classList.toggle('theme-dark');
      try { localStorage.setItem(KEY, on ? 'dark' : 'light'); } catch (e2) {}
    });
  }

  /* Some browsers ignore autoplay until nudged. */
  function bgVideo() {
    document.querySelectorAll('.w-background-video > video').forEach(function (v) {
      v.muted = true;
      var p = v.play();
      if (p && p.catch) p.catch(function () {});
    });
  }

  function init() { reveals(); nav(); counters(); darkMode(); bgVideo(); }
  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', init);
  else init();
})();
