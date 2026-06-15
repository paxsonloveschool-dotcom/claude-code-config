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

    // Private demo page — talk to the bot live (no Facebook needed). Key-gated.
    if (request.method === "GET" && url.pathname === "/demo") {
      if (url.searchParams.get("key") !== env.META_VERIFY_TOKEN) {
        return new Response("forbidden", { status: 403 });
      }
      return new Response(DEMO_HTML, {
        status: 200,
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });
    }

    // Demo backend: run the real decision engine on a typed message. Key-gated.
    if (request.method === "GET" && url.pathname === "/test") {
      if (url.searchParams.get("key") !== env.META_VERIFY_TOKEN) {
        return new Response("forbidden", { status: 403 });
      }
      const q = (url.searchParams.get("q") ?? "").slice(0, 1000);
      if (!q.trim()) return Response.json({ error: "empty message" }, { status: 400 });
      const decision = await decide(env, {
        id: `demo:${Date.now()}`,
        platform: "facebook",
        surface: "dm",
        pageId: HP_DEMO_PAGE_KEY,
        senderId: "demo-visitor",
        text: q,
        username: "demo-visitor",
      });
      return Response.json({
        reply: decision.reply,
        action: decision.action,
        category: decision.category,
        crossSellPartner: decision.crossSellPartner,
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

<<<<<<< HEAD
// The HP Landscaping profile is keyed by this id in knowledge.ts; the demo forces it
// so visitors see HP's real answers regardless of the (not-yet-set) live Page ID.
const HP_DEMO_PAGE_KEY = "REPLACE_WITH_PAGE_ID";

const DEMO_HTML = `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HP Landscaping — AI Assistant Demo</title>
<style>
:root{--bg:#F4F1EA;--ink:#23201b;--accent:#9c6b3f}
*{box-sizing:border-box}
body{font-family:system-ui,Arial,sans-serif;background:var(--bg);color:var(--ink);margin:0;min-height:100vh;display:flex;flex-direction:column}
header{padding:18px 20px;border-bottom:1px solid #e2dccd}
header h1{margin:0;font-size:1.15rem}
header p{margin:4px 0 0;color:#6b6557;font-size:.85rem}
#log{flex:1;overflow-y:auto;padding:18px;max-width:680px;width:100%;margin:0 auto}
.msg{margin:10px 0;display:flex}
.me{justify-content:flex-end}
.bub{padding:10px 14px;border-radius:16px;max-width:80%;line-height:1.45;white-space:pre-wrap}
.me .bub{background:var(--accent);color:#fff;border-bottom-right-radius:4px}
.bot .bub{background:#fff;border:1px solid #e2dccd;border-bottom-left-radius:4px}
.tag{font-size:.7rem;color:#8a8475;margin-top:4px}
form{display:flex;gap:8px;padding:14px;border-top:1px solid #e2dccd;max-width:680px;width:100%;margin:0 auto}
input{flex:1;padding:12px 14px;border:1px solid #cfc8b8;border-radius:22px;font-size:1rem}
button{padding:0 18px;border:0;background:var(--accent);color:#fff;border-radius:22px;font-size:1rem;cursor:pointer}
button:disabled{opacity:.5}
</style></head><body>
<header><h1>HP Landscaping — AI Assistant</h1><p>Live demo. Ask about our services, hours, or area. Try a pricing question too.</p></header>
<div id="log"></div>
<form id="f"><input id="q" placeholder="Type a question…" autocomplete="off" autofocus><button id="b">Send</button></form>
<script>
const key=new URLSearchParams(location.search).get('key');
const log=document.getElementById('log'),f=document.getElementById('f'),q=document.getElementById('q'),b=document.getElementById('b');
function add(t,who,tag){const d=document.createElement('div');d.className='msg '+who;d.innerHTML='<div><div class="bub"></div>'+(tag?'<div class="tag">'+tag+'</div>':'')+'</div>';d.querySelector('.bub').textContent=t;log.appendChild(d);log.scrollTop=log.scrollHeight;}
add("Hey! Thanks for reaching out to HP Landscaping. What can I help you with?","bot","");
f.onsubmit=async e=>{e.preventDefault();const m=q.value.trim();if(!m)return;add(m,"me","");q.value="";b.disabled=true;
try{const r=await fetch('/test?key='+encodeURIComponent(key)+'&q='+encodeURIComponent(m));const j=await r.json();
const tag=j.action==='escalate'?('\\u2192 routed to a human ('+j.category+')'):'';add(j.reply||'(no reply)','bot',tag);}
catch(_){add("(error reaching the bot)","bot","");}
b.disabled=false;q.focus();};
</script></body></html>`;

=======
>>>>>>> origin/main
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
