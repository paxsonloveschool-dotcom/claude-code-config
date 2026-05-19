/* Builds a clean, Webflow-runtime-free static site from _webflow-source/.
 * - Drops the dead .xmas-theme duplicate, unwraps the live .original.hide wrapper
 * - Strips jQuery, Webflow IX2 bundle, webfont.js, waypoints, counterup, data-wf-* attrs
 * - Injects a single canonical header/footer into every content page
 * - Replaces Webflow IX2 scroll reveals + Lottie dark toggle with vanilla hooks
 * Keeps the original CSS class names (the design system CSS is keyed to them).
 */
const cheerio = require('/tmp/np/node_modules/cheerio');
const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, '..', '_webflow-source');
const OUT = path.join(__dirname, '..', 'site');
const GOOGLE_FONTS =
  'https://fonts.googleapis.com/css2?family=Montserrat:ital,wght@0,100..900;1,100..900' +
  '&family=Oswald:wght@200..700&family=Barlow:wght@300;400;500;600;700' +
  '&family=Work+Sans:wght@300;400;500;600;700&family=Lobster&display=swap';

const NAV = [
  ['index.html', 'Home'], ['design.html', 'Design'], ['services.html', 'Services'],
  ['our-work.html', 'Portfolio'], ['our-giving.html', 'Charity'], ['about-us.html', 'About Us'],
  ['blogs.html', 'Blog'], ['faq.html', 'FAQ'], ['career.html', 'Career'],
  ['contact-us.html', 'Contact'],
];

const UTILITY = new Set(['401.html', '404.html']);

function stripRuntime($) {
  // head: webfont loader + touch-detect + Webflow page attrs
  $('script').each((_, el) => {
    const s = $(el);
    const src = s.attr('src') || '';
    const txt = s.html() || '';
    if (
      /webfont|jquery|waypoints|counterup|hp-landscaping-anomaly/i.test(src) ||
      /WebFont\.load|w-mod-|counterUp\(/.test(txt)
    ) {
      s.remove();
    }
  });
  $('html').removeAttr('data-wf-page').removeAttr('data-wf-site').removeAttr('data-wf-domain');
  $('[data-wf-page-id]').removeAttr('data-wf-page-id');
  $('[data-wf-element-id]').removeAttr('data-wf-element-id');
  $('[data-w-id]').removeAttr('data-w-id');

  // Drop dead Webflow IX2 initial-state <style> blocks
  $('style').each((_, el) => {
    const t = $(el).html() || '';
    if (/w-mod-ix|\[data-w-id=/.test(t)) $(el).remove();
  });

  // Localize links that still point at the old Webflow staging domain
  $('a[href]').each((_, el) => {
    const a = $(el);
    const h = a.attr('href') || '';
    const m = h.match(/^https?:\/\/hp-landscaping-anomaly\.webflow\.io(\/[^?#]*)?/i);
    if (m) {
      const p = m[1] || '/';
      a.attr('href', /^\/services\//i.test(p) ? 'services.html' : 'index.html');
    }
  });

  // Google Fonts via stylesheet instead of the JS loader
  if (!$('link[href*="fonts.googleapis.com/css2"]').length) {
    $('head').append(`\n  <link href="${GOOGLE_FONTS}" rel="stylesheet">`);
  }

  // Clean asset paths (hashed Webflow names -> stable names)
  $('link[rel="stylesheet"]').each((_, el) => {
    const h = $(el).attr('href') || '';
    if (/hp-landscaping-anomaly.*\.css/.test(h)) $(el).attr('href', 'css/main.css');
  });

  // Reveal-on-scroll: drop inline opacity:0, tag for the vanilla observer
  $('[style*="opacity:0"], [style*="opacity: 0"]').each((_, el) => {
    const s = $(el);
    let st = (s.attr('style') || '').replace(/opacity:\s*0;?/g, '').trim();
    st ? s.attr('style', st) : s.removeAttr('style');
    s.attr('data-reveal', '');
  });

  // Clean vanilla dark-mode toggle in place of the Lottie widget
  $('.darkify').each((_, el) => {
    $(el).html(
      '<button class="toggle" type="button" aria-label="Toggle dark mode"></button>'
    );
  });

  $('script[src*="d3e54v103j8qbb"], noscript').remove();
  return $;
}

// Pull the canonical header/footer out of index.html (live theme only).
// Header primitives (.top-banner + .cf-navbar-6) are wrapped in .nav-section
// so every page ends up with one identical, normalized chrome.
function extractChrome() {
  const $ = cheerio.load(fs.readFileSync(path.join(SRC, 'index.html'), 'utf8'));
  $('.xmas-theme').remove();
  const $orig = $('.original.hide');
  const scope = $orig.length ? $orig : $('body');
  const banner = $.html(scope.find('.top-banner').first());
  const navbar = $.html(scope.find('.cf-navbar-6').first());
  const header = `<div class="nav-section">${banner}${navbar}</div>`;
  const footer = $.html(scope.find('.footer-section').first());
  return { header, footer };
}

function setActive($, file) {
  $('.cf-nav-menu-4 a.cf-nav-links-3, .footer-nav a, .footer-columns a').each((_, el) => {
    const a = $(el);
    if ((a.attr('href') || '') === file) a.addClass('w--current').attr('aria-current', 'page');
    else a.removeClass('w--current').removeAttr('aria-current');
  });
}

function build() {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(path.join(OUT, 'css'), { recursive: true });
  fs.mkdirSync(path.join(OUT, 'js'), { recursive: true });

  fs.copyFileSync(path.join(SRC, 'css/normalize.css'), path.join(OUT, 'css/normalize.css'));
  fs.copyFileSync(path.join(SRC, 'css/components.css'), path.join(OUT, 'css/components.css'));
  fs.copyFileSync(path.join(SRC, 'css/hp-landscaping-anomaly.css'), path.join(OUT, 'css/main.css'));
  fs.copyFileSync(path.join(__dirname, 'site-runtime.js'), path.join(OUT, 'js/site.js'));

  const chrome = extractChrome();
  const pages = fs.readdirSync(SRC).filter((f) => f.endsWith('.html'));

  for (const file of pages) {
    const $ = cheerio.load(fs.readFileSync(path.join(SRC, file), 'utf8'));
    $('.xmas-theme').remove();
    $('.footer-section-xmas').remove();

    const $orig = $('.original.hide');
    if ($orig.length) {
      $orig.replaceWith($orig.html()); // unwrap live wrapper
    }

    if (!UTILITY.has(file)) {
      // Remove every existing header/footer/toggle primitive, then inject
      // one canonical copy so all pages share identical chrome.
      $('.nav-section, .top-banner, .cf-navbar-6, .footer-section, .darkify').remove();
      $('body').prepend(chrome.header);
      $('body').append(chrome.footer);
      $('body').append('<div class="darkify"><a href="#" class="toggle"></a></div>');
      setActive($, file);
    }

    stripRuntime($);
    $('body').append('\n  <script src="js/site.js" defer></script>\n');

    fs.writeFileSync(path.join(OUT, file), $.html());
  }
  console.log(`Built ${pages.length} pages -> site/`);
}

build();
