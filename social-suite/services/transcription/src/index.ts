import type { Env, TranscriptResult } from "./types";
import { transcribe } from "./whisper";
import { toSrt, toVtt } from "./format";

/**
 * Transcription service.
 *
 *   GET  /          -> health check
 *   POST /transcribe -> audio/video in, timed transcript out
 *
 * Input (any one of):
 *   - multipart/form-data with a `file` field
 *   - JSON body { "url": "https://.../clip.mp3" }  (we fetch it)
 *   - raw audio bytes as the request body (Content-Type: audio/* or video/*)
 *
 * Query params:
 *   - key=<AUTH_KEY>   auth (or send the `x-auth-key` header)
 *   - format=json|srt|vtt   response shape (default json — includes srt & vtt)
 *   - lang=<code>      optional language hint passed to Whisper
 */
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/") {
      return new Response("transcription: ok", { status: 200 });
    }

    if (request.method === "POST" && url.pathname === "/transcribe") {
      return handleTranscribe(request, env, url);
    }

    return new Response("not found", { status: 404 });
  },
} satisfies ExportedHandler<Env>;

function authed(request: Request, url: URL, env: Env): boolean {
  // No key configured = open (dev only; README warns not to deploy this way).
  if (!env.AUTH_KEY) return true;
  const provided = url.searchParams.get("key") ?? request.headers.get("x-auth-key");
  return provided === env.AUTH_KEY;
}

/** Pull audio bytes out of whatever input form the caller used. */
async function readAudio(request: Request): Promise<Uint8Array> {
  const ct = request.headers.get("content-type") ?? "";

  if (ct.includes("multipart/form-data")) {
    const form = await request.formData();
    const file = form.get("file");
    if (!file || typeof file === "string") throw new Error("multipart body needs a `file` field");
    // workers-types narrows the non-string entry to a Blob-like with arrayBuffer().
    return new Uint8Array(await (file as Blob).arrayBuffer());
  }

  if (ct.includes("application/json")) {
    const body = (await request.json()) as { url?: unknown };
    if (typeof body.url !== "string" || !body.url) throw new Error("JSON body needs a `url` string");
    const res = await fetch(body.url);
    if (!res.ok) throw new Error(`fetch of audio url failed: ${res.status}`);
    return new Uint8Array(await res.arrayBuffer());
  }

  // Fall through: treat the raw request body as audio bytes.
  return new Uint8Array(await request.arrayBuffer());
}

async function handleTranscribe(request: Request, env: Env, url: URL): Promise<Response> {
  if (!authed(request, url, env)) return new Response("forbidden", { status: 403 });

  let audio: Uint8Array;
  try {
    audio = await readAudio(request);
  } catch (err) {
    return Response.json({ error: (err as Error).message }, { status: 400 });
  }

  if (!audio.length) return Response.json({ error: "empty audio body" }, { status: 400 });
  const maxBytes = Number(env.MAX_AUDIO_BYTES || "26214400");
  if (audio.length > maxBytes) {
    return Response.json(
      { error: `audio too large: ${audio.length} bytes (max ${maxBytes})` },
      { status: 413 },
    );
  }

  const lang = url.searchParams.get("lang") ?? undefined;
  let t;
  try {
    t = await transcribe(env, audio, lang);
  } catch (err) {
    return Response.json({ error: `transcription failed: ${(err as Error).message}` }, { status: 502 });
  }

  const srt = toSrt(t.segments);
  const vtt = toVtt(t.segments);
  const format = url.searchParams.get("format");

  if (format === "srt") {
    return new Response(srt, {
      status: 200,
      headers: { "Content-Type": "application/x-subrip; charset=utf-8" },
    });
  }
  if (format === "vtt") {
    return new Response(vtt, { status: 200, headers: { "Content-Type": "text/vtt; charset=utf-8" } });
  }

  const result: TranscriptResult = {
    text: t.text,
    language: t.language,
    duration: t.duration,
    segments: t.segments,
    words: t.words,
    srt,
    vtt,
  };
  return Response.json(result);
}
