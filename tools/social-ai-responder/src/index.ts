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

    // Public privacy policy (required for Meta App Review).
    if (request.method === "GET" && url.pathname === "/privacy") {
      return new Response(PRIVACY_HTML, {
        status: 200,
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });
    }

    // Public data deletion instructions (Meta also asks for this).
    if (request.method === "GET" && url.pathname === "/data-deletion") {
      return new Response(DATA_DELETION_HTML, {
        status: 200,
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });
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

const PRIVACY_HTML = `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy Policy — HP Landscaping</title>
<style>body{font-family:system-ui,Arial,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;line-height:1.6;color:#1a1a1a}h1{font-size:1.7rem}h2{font-size:1.15rem;margin-top:1.6em}small{color:#666}</style>
</head><body>
<h1>Privacy Policy</h1>
<small>HP Landscaping &middot; College Station, TX &middot; Last updated: June 2026</small>

<p>HP Landscaping ("we", "us") operates an automated assistant that helps us respond to
messages and comments customers send us on Facebook and Instagram. This policy explains
what information we handle and why.</p>

<h2>What we collect</h2>
<p>When you message or comment on our Facebook or Instagram pages, we receive the content
of your message, your public profile name/username, and the message identifiers Meta
provides. We do not collect your password, payment details, or contact information beyond
what you choose to send us in a message.</p>

<h2>How we use it</h2>
<p>We use your message solely to answer your question, route requests about pricing or
quotes to a human team member, and follow up with you about our landscaping services.
We do not sell your information or use it for advertising.</p>

<h2>How it's processed</h2>
<p>Messages are processed automatically to generate a reply and are stored only briefly to
prevent duplicate responses and to let our team follow up on requests that need a person.
We do not share your information with third parties except the service providers that
operate our messaging assistant (Meta and our cloud/AI hosting providers), who process it
only on our behalf.</p>

<h2>Data retention &amp; deletion</h2>
<p>Routine message-handling data is automatically removed within 30–60 days. You may
request deletion of your data at any time — see our
<a href="/data-deletion">data deletion instructions</a> or contact us below.</p>

<h2>Contact</h2>
<p>HP Landscaping<br>
14801 S Dowling Rd, College Station, TX 77845<br>
Phone: (979) 701-2229<br>
Email: higherpurposelandscaping@gmail.com</p>
</body></html>`;

const DATA_DELETION_HTML = `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data Deletion — HP Landscaping</title>
<style>body{font-family:system-ui,Arial,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;line-height:1.6;color:#1a1a1a}h1{font-size:1.7rem}</style>
</head><body>
<h1>Data Deletion Instructions</h1>
<p>To have any data associated with your messages to HP Landscaping deleted, email
<strong>higherpurposelandscaping@gmail.com</strong> with the subject "Data Deletion" and
the Facebook or Instagram name you messaged us from. We will remove your associated
message data within 30 days and confirm by reply.</p>
<p>HP Landscaping &middot; (979) 701-2229 &middot; College Station, TX</p>
</body></html>`;
