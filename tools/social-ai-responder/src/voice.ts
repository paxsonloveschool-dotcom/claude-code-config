import type { Env, Interaction } from "./types";
import { decide } from "./claude";
import { escalate, logCrossSell } from "./escalate";
import { getProfileByPhone } from "./knowledge";
import { authed, escapeXml, twiml } from "./twilio";

const SAY_VOICE = "Polly.Joanna"; // Twilio neural voice; change as you like.
const MAX_EMPTY_TRIES = 2; // hang up / take a message after this many silent turns.

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

  if (decision.crossSellPartner) {
    ctx.waitUntil(logCrossSell(env, it, decision.crossSellPartner, decision.crossSellReason));
  }

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
      crossSellPartner: "",
      crossSellReason: "",
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
