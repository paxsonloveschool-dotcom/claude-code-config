import type { Env, Interaction } from "./types";
import { decide } from "./claude";
import { parseWebhook, deliverReply, verifySignature, verifySubscription } from "./meta";
import { escalate, listEscalations, listLeads, logCrossSell } from "./escalate";
import { handleVoiceCall, handleVoiceCollect, handleVoicemail } from "./voice";
import { handleSms } from "./sms";

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // Health check
    if (request.method === "GET" && url.pathname === "/") {
      return new Response("social-ai-responder: ok", { status: 200 });
    }

    // Owner-facing: read the escalation queue. Protect with ?key=<META_VERIFY_TOKEN>.
    if (request.method === "GET" && url.pathname === "/escalations") {
      if (url.searchParams.get("key") !== env.META_VERIFY_TOKEN) {
        return new Response("forbidden", { status: 403 });
      }
      return Response.json(await listEscalations(env));
    }

    // Owner-facing: cross-sell lead queue. Protect with ?key=<META_VERIFY_TOKEN>.
    if (request.method === "GET" && url.pathname === "/leads") {
      if (url.searchParams.get("key") !== env.META_VERIFY_TOKEN) {
        return new Response("forbidden", { status: 403 });
      }
      return Response.json(await listLeads(env));
    }

    // Meta webhook verification handshake
    if (request.method === "GET" && url.pathname === "/webhook") {
      const challenge = verifySubscription(url, env);
      return challenge
        ? new Response(challenge, { status: 200 })
        : new Response("verification failed", { status: 403 });
    }

    // Meta webhook events
    if (request.method === "POST" && url.pathname === "/webhook") {
      const raw = await request.text();
      const ok = await verifySignature(raw, request.headers.get("x-hub-signature-256"), env.META_APP_SECRET);
      if (!ok) return new Response("bad signature", { status: 401 });

      let body: unknown;
      try {
        body = JSON.parse(raw);
      } catch {
        return new Response("bad json", { status: 400 });
      }

      const interactions = parseWebhook(body);
      // Process after responding — Meta requires a fast 200 or it retries/disables.
      ctx.waitUntil(processAll(env, interactions));
      return new Response("EVENT_RECEIVED", { status: 200 });
    }

    // ---- Phase 2: Twilio Voice (phone calls) ----
    // Incoming call: greet + start listening.
    if (request.method === "POST" && url.pathname === "/voice") {
      return handleVoiceCall(request, env);
    }
    // Speech turn: Twilio posts the transcript; we answer or transfer.
    if (request.method === "POST" && url.pathname === "/voice/collect") {
      return handleVoiceCollect(request, env, ctx);
    }
    // Voicemail recording finished.
    if (request.method === "POST" && url.pathname === "/voice/voicemail") {
      return handleVoicemail(request, env, ctx);
    }

    // Inbound SMS (texts).
    if (request.method === "POST" && url.pathname === "/sms") {
      return handleSms(request, env, ctx);
    }

    return new Response("not found", { status: 404 });
  },
} satisfies ExportedHandler<Env>;

async function processAll(env: Env, interactions: Interaction[]): Promise<void> {
  for (const it of interactions) {
    try {
      // Dedup: Meta re-delivers on any non-200 / timeout. Skip seen event ids.
      const seenKey = `seen:${it.id}`;
      if (await env.STATE.get(seenKey)) continue;
      await env.STATE.put(seenKey, "1", { expirationTtl: 60 * 60 * 24 * 3 });

      const decision = await decide(env, it);

      // Send the reply. For comments: basic questions are answered publicly, but
      // pricing/personal ones (escalated) are sent as a private DM instead.
      if (decision.reply?.trim()) {
        await deliverReply(env, it, decision.reply.trim(), decision.action === "escalate");
      }

      if (decision.action === "escalate") {
        await escalate(env, it, decision);
      }

      // Cross-sell: flag a sister-business lead (separate from helping this customer).
      if (decision.crossSellPartner) {
        await logCrossSell(env, it, decision.crossSellPartner, decision.crossSellReason);
      }
    } catch (err) {
      // Last-ditch: record so nothing is silently dropped.
      await escalate(env, it, {
        action: "escalate",
        category: "processing_error",
        reply: "",
        confidence: 0,
        reason: `Unhandled error: ${(err as Error).message}`,
        crossSellPartner: "",
        crossSellReason: "",
      });
    }
  }
}
