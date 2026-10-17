/* Generates placeholder media for every asset the rebuilt site references,
 * so site/ renders without broken images/videos. No external tools: PNGs are
 * built with Node's zlib, SVGs are written as text, videos are tiny stubs.
 * Deterministic — colors are hashed from the filename so rebuilds are stable.
 */
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const OUT = path.join(__dirname, '..', 'site');
const refsFile = process.argv[2] || '/tmp/assets.txt';

// Earthy / landscaping-ish palette
const PALETTE = [
  [47, 186, 84], [0, 129, 81], [24, 98, 27], [10, 21, 17],
  [120, 144, 96], [86, 125, 70], [201, 173, 122], [70, 70, 70],
];

function hash(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = (h * 16777619) >>> 0; }
  return h >>> 0;
}

function crc32(buf) {
  let c = ~0;
  for (let i = 0; i < buf.length; i++) {
    c ^= buf[i];
    for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1));
  }
  return (~c) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length, 0);
  const td = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td), 0);
  return Buffer.concat([len, td, crc]);
}

// Solid-color PNG with a soft diagonal band so placeholders read as "photos".
function makePNG(w, h, rgb) {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; ihdr[9] = 2; // 8-bit, truecolor RGB
  const [r, g, b] = rgb;
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) {
    const row = y * (w * 3 + 1);
    raw[row] = 0; // filter: none
    for (let x = 0; x < w; x++) {
      const t = ((x + y) % 90) < 45 ? 1 : 0.86; // subtle band
      const o = row + 1 + x * 3;
      raw[o] = Math.min(255, r * t);
      raw[o + 1] = Math.min(255, g * t);
      raw[o + 2] = Math.min(255, b * t);
    }
  }
  return Buffer.concat([
    sig, chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

function makeSVG(name, rgb) {
  const [r, g, b] = rgb;
  const c = `rgb(${r},${g},${b})`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">` +
    `<rect width="600" height="400" fill="${c}"/>` +
    `<rect width="600" height="400" fill="none" stroke="#ffffff" stroke-opacity="0.25" stroke-width="2"/>` +
    `<text x="300" y="205" font-family="Oswald,Arial,sans-serif" font-size="34" font-weight="600" ` +
    `fill="#ffffff" text-anchor="middle">HP</text></svg>\n`;
}

// Minimal 1-frame black MP4 + WebM. Browsers may not decode these; the build
// step gives every <video> a local poster, so the visual holds regardless.
const MP4 = Buffer.from(
  'AAAAHGZ0eXBtcDQyAAAAAW1wNDJpc29tYXZjMQAAAAhmcmVlAAAALW1kYXQAAAGzABBA' +
  'AAAGcGljdAAAAAAAAAABAAAA3G1vb3YAAABsbXZoZAAAAAAAAAAAAAAAAAAAA+gAAAAA' +
  'AAEAAAEAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAEAAAAAA' +
  'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAA', 'base64');
const WEBM = Buffer.from(
  'GkXfo59ChoEBQveBAULygQRC84EIQoKEd2VibUKHgQRChYECGFOAZwH/////////FUmp' +
  'Zpkq17GDD0JATYCGQ2hyb21lV0GHQ2hyb21lFlSua7+uvdeBAXPFh5xJGw==', 'base64');

const refs = fs.readFileSync(refsFile, 'utf8').split('\n').filter(Boolean);
let imgN = 0, svgN = 0, vidN = 0;

for (const ref of refs) {
  for (const one of ref.split(',')) {
    const rel = one.trim();
    if (!rel) continue;
    const dest = path.join(OUT, rel);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    const ext = path.extname(rel).toLowerCase();
    const rgb = PALETTE[hash(path.basename(rel)) % PALETTE.length];
    if (ext === '.svg') { fs.writeFileSync(dest, makeSVG(rel, rgb)); svgN++; }
    else if (ext === '.mp4') { fs.writeFileSync(dest, MP4); vidN++; }
    else if (ext === '.webm') { fs.writeFileSync(dest, WEBM); vidN++; }
    else { fs.writeFileSync(dest, makePNG(1280, 854, rgb)); imgN++; } // png/jpg/webp/gif
  }
}

// One shared branded poster for video sections.
fs.writeFileSync(path.join(OUT, 'images', '_poster.png'), makePNG(1600, 900, PALETTE[0]));
console.log(`images:${imgN} svg:${svgN} video:${vidN} + _poster.png`);
