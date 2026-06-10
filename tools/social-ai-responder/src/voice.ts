import type { Env, Interaction } from "./types";
import { decide } from "./claude";
import { escalate } from "./escalate";
import { getProfileByPhone } from "./knowledge";

const SAY_VOICE = "Polly.Joanna"; // Twilio neural voice; change as you like.
const MAX_EMPTY_TRIES = 2; // hang up / take a message after this many silent turns.

// ---------------------------------------------------------------------------
// TwiML helpers
// ---------------------------------------------------------------------------

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function twiml(inner: string): Response {
  const xml = `<?xml version="1.0" encoding="UTF-8"?><Response>${inner}</Response>`;
  return new Response(xml, { status: 200, headers: { "Content-Type": "text/xml" } });
}

function say(text: string): string {
  return `<Say voice="${SAY_VOICE}">${escapeXml(text)}</Say>`;
}

/** Speak `prompt`, then listen for the next utterance (sends transcript to /voice/collect). */
function gather(prompt: string, tries: number): string {
  const action = `/voice/collect?tries=${tries}`;
  return (
    `<Gather input="speech" speechTimeout="auto" language="en-US" ` +
    `action="${action}" method="POST" actionOnEmptyResult="true">${say(prompt)}</Gather>`
  );
}

// ---------------------------------------------------------------------------
// Twilio request validation
// ---------------------------------------------------------------------------

/** Full URL Twilio signed against (honor a proxy override if configured). */
function signedUrl(request: Request, env: Env): string {
  const url = new URL(request.url);
  if (env.PUBLIC_BASE_URL) {
    return env.PUBLIC_BASE_URL.replace(/\/$/, "") + url.pathname + url.search;
  }
  return request.url;
}

/**
 * Verify Twilio's X-Twilio-Signature: HMAC-SHA1 of (url + sorted key+value pairs),
 * base64-encoded, keyed by the auth token. https://www.twilio.com/docs/usage/security
 */
async function verifyTwilio(
  url: string,
  params: Record<string, string>,
  signature: string | null,
  authToken: string,
): Promise<boolean> {
  if (!signature) return false;
  let data = url;
  for (const key of Object.keys(params).sort()) data += key + params[key];

  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(authToken),
    { name: "HMAC", hash: "SHA-1" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign("HMAC", cryptoKey, new TextEncoder().encode(data));
  const expected = btoa(String.fromCharCode(...new Uint8Array(mac)));

  if (expected.length !== signature.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= expected.charCodeAt(i) ^ signature.charCodeAt(i);
  return diff === 0;
}

/** Read a Twilio form-encoded POST body into a flat param map. */
async function formParams(request: Request): Promise<Record<string, string>> {
  const form = await request.formData();
  const out: Record<string, string> = {};
  for (const [k, v] of form.entries()) out[k] = typeof v === "string" ? v : "";
  return out;
}

async function authed(
  request: Request,
  env: Env,
): Promise<{ ok: boolean; params: Record<string, string> }> {
  const params = await formParams(request);
  // No token configured → voice is effectively disabled; reject.
  if (!env.TWILIO_AUTH_TOKEN) return { ok: false, params };
  const ok = await verifyTwilio(
    signedUrl(request, env),
    params,
    request.headers.get("x-twilio-signature"),
    env.TWILIO_AUTH_TOKEN,
  );
  return { ok, params };
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

/** Incoming call: greet and start listening. */
export async function handleVoiceCall(request: Request, env: Env): Promise<Response> {
  const { ok, params } = await authed(request, env);
  if (!ok) return new Response("forbidden", { status: 403 });

  const to = params.To ?? "";
  const { profile } = getProfileByPhone(to);

  if (!profile.voice) {
    return twiml(say("Sorry, this line isn't taking calls right now. Goodbye.") + "<Hangup/>");
  }
  return twiml(gather(profile.voice.greeting, 0));
}

/** A speech turn: answer the question, transfer, or take a message. */
export async function handleVoiceCollect(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<Response> {
  const { ok, params } = await authed(request, env);
  if (!ok) return new Response("forbidden", { status: 403 });

  const url = new URL(request.url);
  const tries = Number(url.searchParams.get("tries") ?? "0");
  const to = params.To ?? "";
  const from = params.From ?? "";
  const callSid = params.CallSid ?? "";
  const speech = (params.SpeechResult ?? "").trim();
  const { pageId, profile } = getProfileByPhone(to);

  // Silence: reprompt, then give up to voicemail/hangup.
  if (!speech) {
    if (tries + 1 >= MAX_EMPTY_TRIES) return endCall(profile);
    return twiml(gather("Sorry, I didn't catch that. How can I help?", tries + 1));
  }

  const it: Interaction = {
    id: `${callSid}:${Date.now()}`,
    platform: "phone",
    surface: "call",
    pageId,
    senderId: from,
    text: speech,
    username: from,
  };

  const decision = await decide(env, it);

  if (decision.action === "escalate") {
    // Record the escalation out-of-band so TwiML returns fast.
    ctx.waitUntil(escalate(env, it, decision));

    const transfer = profile.voice?.transferNumber;
    if (transfer) {
      return twiml(
        say(decision.reply || "Let me connect you with someone who can help. One moment.") +
          `<Dial>${escapeXml(transfer)}</Dial>`,
      );
    }
    // No transfer number → take a voicemail.
    return twiml(
      say(decision.reply || "Let me take a message and someone will call you right back.") +
        `<Record action="/voice/voicemail?to=${encodeURIComponent(to)}" method="POST" ` +
        `maxLength="120" playBeep="true" finishOnKey="#"/>` +
        say("Sorry, I didn't get a recording. Goodbye.") +
        "<Hangup/>",
    );
  }

  // Auto-answer and keep the conversation going.
  return twiml(gather(decision.reply || "Is there anything else I can help with?", 0));
}

/** Voicemail finished: log it for the owner and say goodbye. */
export async function handleVoicemail(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<Response> {
  const { ok, params } = await authed(request, env);
  if (!ok) return new Response("forbidden", { status: 403 });

  const url = new URL(request.url);
  const to = url.searchParams.get("to") ?? params.To ?? "";
  const from = params.From ?? "";
  const recording = params.RecordingUrl ?? "";
  const { pageId } = getProfileByPhone(to);

  const it: Interaction = {
    id: `${params.CallSid ?? "call"}:voicemail`,
    platform: "phone",
    surface: "call",
    pageId,
    senderId: from,
    text: `Voicemail recording: ${recording}.mp3`,
    username: from,
  };
  ctx.waitUntil(
    escalate(env, it, {
      action: "escalate",
      category: "voicemail",
      reply: "",
      confidence: 0,
      reason: "Caller left a voicemail — listen and call back.",
    }),
  );

  return twiml(say("Thanks! Someone will call you back shortly. Goodbye.") + "<Hangup/>");
}

// ---------------------------------------------------------------------------

function endCall(profile: ReturnType<typeof getProfileByPhone>["profile"]): Response {
  const transfer = profile.voice?.transferNumber;
  if (transfer) {
    return twiml(
      say("Let me connect you with someone. One moment.") + `<Dial>${escapeXml(transfer)}</Dial>`,
    );
  }
  return twiml(say("I'll have someone reach out. Thanks for calling. Goodbye.") + "<Hangup/>");
}
