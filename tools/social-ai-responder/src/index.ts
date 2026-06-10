import type { Decision, Env, Interaction } from "./types";
import { decide } from "./claude";
import { parseWebhook, reply, verifySignature, verifySubscription } from "./meta";

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

      // Send the reply (auto-answer, or a friendly holding message on escalations).
      if (decision.reply?.trim()) {
        await reply(env, it, decision.reply.trim());
      }

      if (decision.action === "escalate") {
        await escalate(env, it, decision);
      }
    } catch (err) {
      // Last-ditch: record so nothing is silently dropped.
      await escalate(env, it, {
        action: "escalate",
        category: "processing_error",
        reply: "",
        confidence: 0,
        reason: `Unhandled error: ${(err as Error).message}`,
      });
    }
  }
}

interface EscalationRecord {
  at: string;
  it: Interaction;
  decision: Decision;
}

async function escalate(env: Env, it: Interaction, decision: Decision): Promise<void> {
  const record: EscalationRecord = { at: new Date().toISOString(), it, decision };

  // 1) Persist to KV so the owner can review via /escalations.
  await env.STATE.put(`esc:${Date.now()}:${it.id}`, JSON.stringify(record), {
    expirationTtl: 60 * 60 * 24 * 30,
  });

  // 2) Optional push notification (Slack/Discord/email-relay webhook).
  if (env.ESCALATION_WEBHOOK_URL) {
    const summary =
      `🔔 *Needs you* — ${it.platform}/${it.surface} (${decision.category})\n` +
      `From: ${it.username ?? it.senderId}\n` +
      `Message: ${it.text}\n` +
      `Why: ${decision.reason}\n` +
      `Holding reply sent: ${decision.reply || "(none)"}`;
    try {
      await fetch(env.ESCALATION_WEBHOOK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: summary, record }),
      });
    } catch {
      /* non-fatal: it's still in KV */
    }
  }
}

async function listEscalations(env: Env): Promise<EscalationRecord[]> {
  const list = await env.STATE.list({ prefix: "esc:" });
  const records: EscalationRecord[] = [];
  for (const k of list.keys) {
    const v = await env.STATE.get(k.name);
    if (v) records.push(JSON.parse(v) as EscalationRecord);
  }
  return records.sort((a, b) => b.at.localeCompare(a.at));
}
