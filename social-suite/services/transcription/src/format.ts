import type { Segment, Word } from "./types";

/** Seconds -> "HH:MM:SS,mmm" (SRT) or "HH:MM:SS.mmm" (VTT). */
function stamp(seconds: number, sep: "," | "."): string {
  const s = Math.max(0, seconds);
  const ms = Math.round((s - Math.floor(s)) * 1000);
  const total = Math.floor(s);
  const hh = Math.floor(total / 3600);
  const mm = Math.floor((total % 3600) / 60);
  const ss = total % 60;
  const p2 = (n: number) => String(n).padStart(2, "0");
  return `${p2(hh)}:${p2(mm)}:${p2(ss)}${sep}${String(ms).padStart(3, "0")}`;
}

/** Render cues as a SubRip (.srt) string. */
export function toSrt(segments: Segment[]): string {
  return segments
    .map((seg, i) => `${i + 1}\n${stamp(seg.start, ",")} --> ${stamp(seg.end, ",")}\n${seg.text}\n`)
    .join("\n");
}

/** Render cues as a WebVTT (.vtt) string. */
export function toVtt(segments: Segment[]): string {
  const body = segments
    .map((seg) => `${stamp(seg.start, ".")} --> ${stamp(seg.end, ".")}\n${seg.text}`)
    .join("\n\n");
  return `WEBVTT\n\n${body}\n`;
}

/**
 * Group word-level timing into readable caption cues, breaking when a cue would
 * exceed maxChars or maxSecs, and preferring to break right after sentence-ending
 * punctuation so cues don't split mid-thought.
 */
export function cuesFromWords(words: Word[], maxChars: number, maxSecs: number): Segment[] {
  const cues: Segment[] = [];
  let cur: Word[] = [];

  const flush = () => {
    if (!cur.length) return;
    const first = cur[0]!;
    const last = cur[cur.length - 1]!;
    cues.push({
      start: first.start,
      end: last.end,
      text: cur.map((w) => w.word).join(" ").replace(/\s+([,.!?;:])/g, "$1"),
      words: cur,
    });
    cur = [];
  };

  for (const w of words) {
    const start = cur.length ? cur[0]!.start : w.start;
    const prospectiveChars = cur.map((c) => c.word).join(" ").length + w.word.length + 1;
    const prospectiveSecs = w.end - start;
    if (cur.length && (prospectiveChars > maxChars || prospectiveSecs > maxSecs)) flush();
    cur.push(w);
    if (/[.!?]$/.test(w.word)) flush();
  }
  flush();
  return cues;
}

/**
 * A model segment may be a full sentence too long for one on-screen line. If it
 * has word timing, re-chunk it; otherwise return it as-is (can't split safely).
 */
export function splitLongCue(seg: Segment, maxChars: number, maxSecs: number): Segment[] {
  const tooLong = seg.text.length > maxChars || seg.end - seg.start > maxSecs;
  if (!tooLong) return [seg];
  if (seg.words && seg.words.length) return cuesFromWords(seg.words, maxChars, maxSecs);
  return [seg];
}
