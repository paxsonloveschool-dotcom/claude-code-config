import type { Env, Segment, Word } from "./types";
import { cuesFromWords, splitLongCue } from "./format";

/** Raw-ish shape Whisper models return (fields vary by model). */
interface WhisperRaw {
  text?: string;
  vtt?: string;
  words?: Array<{ word?: string; start?: number; end?: number }>;
  segments?: Array<{
    start?: number;
    end?: number;
    text?: string;
    words?: Array<{ word?: string; start?: number; end?: number }>;
  }>;
  transcription_info?: { language?: string; duration?: number };
}

/** What `transcribe()` hands back before SRT/VTT rendering. */
export interface NormalizedTranscript {
  text: string;
  language?: string;
  duration?: number;
  segments: Segment[];
  words: Word[];
}

function isTurbo(model: string): boolean {
  return model.includes("turbo");
}

/** Base64-encode bytes without blowing the stack on large inputs. */
function toBase64(bytes: Uint8Array): string {
  let bin = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(bin);
}

function num(v: unknown): number | undefined {
  return typeof v === "number" && Number.isFinite(v) ? v : undefined;
}

/** Coerce a model's loose word list into clean {word,start,end} entries. */
function cleanWords(raw: WhisperRaw["words"]): Word[] {
  if (!Array.isArray(raw)) return [];
  const out: Word[] = [];
  for (const w of raw) {
    const start = num(w?.start);
    const end = num(w?.end);
    const word = typeof w?.word === "string" ? w.word : "";
    if (start === undefined || end === undefined || !word.trim()) continue;
    out.push({ word: word.trim(), start, end });
  }
  return out;
}

/**
 * Turn whatever Whisper returned into clean segments + words. Preference order:
 *   1. model segments (re-split if any single cue runs too long), else
 *   2. word-level timing re-chunked into readable cues, else
 *   3. one untimed segment holding the full text.
 */
function normalize(raw: WhisperRaw, env: Env): NormalizedTranscript {
  const maxChars = Number(env.MAX_CUE_CHARS || "42");
  const maxSecs = Number(env.MAX_CUE_SECONDS || "6");
  const text = (raw.text ?? "").trim();
  const language = raw.transcription_info?.language;
  const duration = num(raw.transcription_info?.duration);

  const allWords: Word[] = [];
  let segments: Segment[] = [];

  if (Array.isArray(raw.segments) && raw.segments.length) {
    for (const s of raw.segments) {
      const start = num(s?.start);
      const end = num(s?.end);
      const segText = typeof s?.text === "string" ? s.text.trim() : "";
      if (start === undefined || end === undefined || !segText) continue;
      const words = cleanWords(s?.words);
      allWords.push(...words);
      // A whole sentence-segment can be too long for one on-screen cue; re-split
      // using word timing when we have it.
      segments.push(...splitLongCue({ start, end, text: segText, words }, maxChars, maxSecs));
    }
  }

  if (!segments.length) {
    const words = cleanWords(raw.words);
    allWords.push(...words);
    if (words.length) {
      segments = cuesFromWords(words, maxChars, maxSecs);
    } else if (text) {
      // No timing at all — emit one cue so downstream still gets the text.
      segments = [{ start: 0, end: duration ?? 0, text }];
    }
  }

  return { text, language, duration, segments, words: allWords };
}

/**
 * Run the configured Whisper model on raw audio bytes and return a normalized,
 * caption-ready transcript. Throws on a missing AI binding or model error.
 */
export async function transcribe(env: Env, audio: Uint8Array, lang?: string): Promise<NormalizedTranscript> {
  if (!env.AI) throw new Error("Workers AI binding missing (set [ai] binding in wrangler.toml)");
  const model = env.WHISPER_MODEL || "@cf/openai/whisper-large-v3-turbo";

  // Turbo (large-v3) takes base64; the base whisper model takes a byte array.
  const input: Record<string, unknown> = isTurbo(model)
    ? { audio: toBase64(audio) }
    : { audio: Array.from(audio) };
  if (lang) input.language = lang;

  const raw = (await env.AI.run(model as Parameters<Ai["run"]>[0], input)) as WhisperRaw;
  return normalize(raw, env);
}
