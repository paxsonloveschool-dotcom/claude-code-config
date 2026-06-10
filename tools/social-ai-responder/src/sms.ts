import type { Env, Interaction } from "./types";
import { decide } from "./claude";
import { escalate, logCrossSell } from "./escalate";
import { getProfileByPhone } from "./knowledge";
import { authed, escapeXml, twiml } from "./twilio";

/** Build a TwiML SMS reply (the message Twilio sends back to the customer). */
function message(text: string): string {
  return text ? `<Message>${escapeXml(text)}</Message>` : "";
}

/**
 * Inbound SMS ("text"). Same hybrid brain as DMs: auto-reply FAQs, but for pricing/
 * quotes/complaints we escalate — the customer gets a human-handoff holding text and
 * the owner is texted so a real person responds (never the AI for those).
 */
export async function handleSms(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
  const { ok, params } = await authed(request, env);
  if (!ok) return new Response("forbidden", { status: 403 });

  const from = params.From ?? "";
  const to = params.To ?? "";
  const body = (params.Body ?? "").trim();
  const sid = params.MessageSid ?? `${from}:${Date.now()}`;
  if (!body) return twiml("");

  // Dedup Twilio retries.
  const seenKey = `seen:sms:${sid}`;
  if (await env.STATE.get(seenKey)) return twiml("");
  await env.STATE.put(seenKey, "1", { expirationTtl: 60 * 60 * 24 * 3 });

  const { pageId } = getProfileByPhone(to);
  const it: Interaction = {
    id: sid,
    platform: "sms",
    surface: "text",
    pageId,
    senderId: from,
    text: body,
    username: from,
  };

  const decision = await decide(env, it);

  // Escalations: notify a human out-of-band; the customer still gets the holding text.
  if (decision.action === "escalate") {
    ctx.waitUntil(escalate(env, it, decision));
  }
  if (decision.crossSellPartner) {
    ctx.waitUntil(logCrossSell(env, it, decision.crossSellPartner, decision.crossSellReason));
  }

  return twiml(message(decision.reply || "Thanks! Someone from our team will text you right back."));
}
