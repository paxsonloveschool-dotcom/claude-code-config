/** Cloudflare bindings + config available on `env`. */
export interface Env {
  /** Workers AI binding (set by `[ai]` in wrangler.toml). */
  AI: Ai;
  /** Gates POST /transcribe. Secret — set with `wrangler secret put AUTH_KEY`. */
  AUTH_KEY?: string;
  /** Whisper model id. Default: @cf/openai/whisper-large-v3-turbo. */
  WHISPER_MODEL?: string;
  /** Max characters per re-chunked caption cue. */
  MAX_CUE_CHARS?: string;
  /** Max seconds per re-chunked caption cue. */
  MAX_CUE_SECONDS?: string;
  /** Hard ceiling on accepted audio size, in bytes. */
  MAX_AUDIO_BYTES?: string;
}

/** A single word with its start/end offset in seconds. */
export interface Word {
  word: string;
  start: number;
  end: number;
}

/** A timed cue: one subtitle line spanning [start, end] seconds. */
export interface Segment {
  start: number;
  end: number;
  text: string;
  words?: Word[];
}

/**
 * The stable contract this service returns and downstream services
 * (caption/burn-in) consume. Keep additive — don't break field shapes.
 */
export interface TranscriptResult {
  /** Full plain-text transcript. */
  text: string;
  /** Detected language code, when Whisper reports one. */
  language?: string;
  /** Audio duration in seconds, when reported. */
  duration?: number;
  /** Timed cues, shaped for readable on-screen captions. */
  segments: Segment[];
  /** Word-level timing, when the model provides it (else empty). */
  words: Word[];
  /** Rendered SubRip (.srt) subtitle string. */
  srt: string;
  /** Rendered WebVTT (.vtt) subtitle string. */
  vtt: string;
}
