/* ============================================================= */
/*  TROPHY EXTERIORS — Shared JS (vanilla, no dependencies)      */
/* ============================================================= */
(function () {
  'use strict';

  var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ----------------------------------------------------------- */
  /*  Footer year                                                */
  /* ----------------------------------------------------------- */
  var yearEl = document.getElementById('year');
  if (yearEl) { yearEl.textContent = new Date().getFullYear(); }

  /* ----------------------------------------------------------- */
  /*  Sticky header state change on scroll                       */
  /* ----------------------------------------------------------- */
  var header = document.getElementById('siteHeader');
  if (header) {
    var onScroll = function () {
      if (window.scrollY > 60) {
        header.classList.add('is-scrolled');
      } else {
        header.classList.remove('is-scrolled');
      }
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  /* ----------------------------------------------------------- */
  /*  Mega-menu aria-expanded sync (hover + focus)               */
  /* ----------------------------------------------------------- */
  var megaItems = document.querySelectorAll('.has-mega');
  megaItems.forEach(function (item) {
    var trigger = item.querySelector('a[aria-haspopup]');
    if (!trigger) return;
    var setState = function (open) { trigger.setAttribute('aria-expanded', String(open)); };
    item.addEventListener('mouseenter', function () { setState(true); });
    item.addEventListener('mouseleave', function () { setState(false); });
    item.addEventListener('focusin', function () { setState(true); });
    item.addEventListener('focusout', function (e) {
      if (!item.contains(e.relatedTarget)) { setState(false); }
    });
  });

  /* ----------------------------------------------------------- */
  /*  Mobile menu                                                */
  /* ----------------------------------------------------------- */
  var hamburger = document.getElementById('hamburger');
  var mobileMenu = document.getElementById('mobileMenu');
  var overlay = document.getElementById('mobileOverlay');

  function openMenu() {
    mobileMenu.classList.add('is-open');
    hamburger.classList.add('is-open');
    overlay.hidden = false;
    requestAnimationFrame(function () { overlay.classList.add('is-open'); });
    hamburger.setAttribute('aria-expanded', 'true');
    hamburger.setAttribute('aria-label', 'Close menu');
    mobileMenu.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }
  function closeMenu() {
    mobileMenu.classList.remove('is-open');
    hamburger.classList.remove('is-open');
    overlay.classList.remove('is-open');
    hamburger.setAttribute('aria-expanded', 'false');
    hamburger.setAttribute('aria-label', 'Open menu');
    mobileMenu.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    window.setTimeout(function () {
      if (!mobileMenu.classList.contains('is-open')) { overlay.hidden = true; }
    }, 320);
  }

  if (hamburger && mobileMenu && overlay) {
    hamburger.addEventListener('click', function () {
      if (mobileMenu.classList.contains('is-open')) { closeMenu(); } else { openMenu(); }
    });
    overlay.addEventListener('click', closeMenu);
    mobileMenu.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', closeMenu);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && mobileMenu.classList.contains('is-open')) { closeMenu(); }
    });
  }

  /* ----------------------------------------------------------- */
  /*  Scroll-triggered reveals (trigger once)                    */
  /* ----------------------------------------------------------- */
  var revealEls = document.querySelectorAll('.reveal');
  if (prefersReducedMotion || !('IntersectionObserver' in window)) {
    revealEls.forEach(function (el) { el.classList.add('is-visible'); });
  } else {
    var revealObserver = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -8% 0px' });
    revealEls.forEach(function (el) { revealObserver.observe(el); });
  }

  /* ----------------------------------------------------------- */
  /*  Animated stat count-up                                     */
  /* ----------------------------------------------------------- */
  function animateCount(el) {
    var target = parseFloat(el.getAttribute('data-count-to'));
    var suffix = el.getAttribute('data-suffix') || '';
    var decimals = parseInt(el.getAttribute('data-decimals') || '0', 10);

    // If the target isn't a real number (placeholder left in), skip animation.
    if (isNaN(target)) { return; }

    var duration = 1600;
    var start = null;
    function frame(ts) {
      if (start === null) { start = ts; }
      var progress = Math.min((ts - start) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      var value = target * eased;
      el.textContent = value.toFixed(decimals) + suffix;
      if (progress < 1) { requestAnimationFrame(frame); }
      else { el.textContent = target.toFixed(decimals) + suffix; }
    }
    requestAnimationFrame(frame);
  }

  var statEls = document.querySelectorAll('.stat__number');
  if (!prefersReducedMotion && 'IntersectionObserver' in window) {
    var statObserver = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          animateCount(entry.target);
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.5 });
    statEls.forEach(function (el) { statObserver.observe(el); });
  }
  // Reduced motion: leave the placeholder/static text in place (no animation).

  /* ----------------------------------------------------------- */
  /*  Estimate form — client-side validation only                */
  /* ----------------------------------------------------------- */
  var form = document.getElementById('estimateForm');
  if (form) {
    var success = document.getElementById('estimateSuccess');

    var validators = {
      'ef-name': function (v) { return v.trim().length >= 2 ? '' : 'Please enter your name.'; },
      'ef-email': function (v) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim()) ? '' : 'Please enter a valid email address.';
      },
      'ef-phone': function (v) {
        var digits = v.replace(/\D/g, '');
        return digits.length >= 10 ? '' : 'Please enter a valid phone number.';
      },
      'ef-address': function (v) { return v.trim().length >= 5 ? '' : 'Please enter your address.'; }
    };

    function validateField(input) {
      var fn = validators[input.id];
      if (!fn) return true;
      var msg = fn(input.value);
      var errEl = form.querySelector('[data-error-for="' + input.id + '"]');
      if (msg) {
        input.classList.add('is-invalid');
        input.setAttribute('aria-invalid', 'true');
        if (errEl) { errEl.textContent = msg; }
        return false;
      }
      input.classList.remove('is-invalid');
      input.removeAttribute('aria-invalid');
      if (errEl) { errEl.textContent = ''; }
      return true;
    }

    Object.keys(validators).forEach(function (id) {
      var input = document.getElementById(id);
      if (input) {
        input.addEventListener('blur', function () { validateField(input); });
        input.addEventListener('input', function () {
          if (input.classList.contains('is-invalid')) { validateField(input); }
        });
      }
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var allValid = true;
      var firstInvalid = null;
      Object.keys(validators).forEach(function (id) {
        var input = document.getElementById(id);
        if (input && !validateField(input)) {
          allValid = false;
          if (!firstInvalid) { firstInvalid = input; }
        }
      });
      if (!allValid) {
        if (success) { success.hidden = true; }
        if (firstInvalid) { firstInvalid.focus(); }
        return;
      }
      // No backend — confirm client-side and reset.
      form.reset();
      if (success) { success.hidden = false; }
    });
  }

})();
