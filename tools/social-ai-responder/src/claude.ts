import Anthropic from "@anthropic-ai/sdk";
import type { Decision, Env, Interaction } from "./types";
import { getProfile, type BusinessProfile } from "./knowledge";

const DECISION_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    action: { type: "string", enum: ["auto_reply", "escalate"] },
    category: { type: "string" },
    reply: { type: "string" },
    confidence: { type: "number" },
    reason: { type: "string" },
    crossSellPartner: { type: "string" },
    crossSellReason: { type: "string" },
  },
  required: [
    "action",
    "category",
    "reply",
    "confidence",
    "reason",
    "crossSellPartner",
    "crossSellReason",
  ],
} as const;

function systemPrompt(p: BusinessProfile, surface: "dm" | "comment" | "call" | "text"): string {
  const faq = p.faq.map((f) => `Q: ${f.q}\nA: ${f.a}`).join("\n\n");
  const escalate = p.escalateWhen.map((e) => `- ${e}`).join("\n");
  const examples = (p.styleExamples ?? [])
    .map((e) => `Customer: ${e.customer}\nUs: ${e.reply}`)
    .join("\n\n");
  const emojiRule = p.useEmojis
    ? `A light, natural emoji is fine when it fits — don't overdo it.`
    : `No emojis unless the customer used them first.`;
  const crossSell = (p.crossSell ?? [])
    .map((c) => `- ${c.partner}: if they mention ${c.signals.join(", ")}`)
    .join("\n");
  const channel =
    surface === "call"
      ? `You are on a LIVE PHONE CALL. Your reply is read aloud by text-to-speech: speak in plain spoken sentences, no markdown, no links, no emojis, 1-2 short sentences, and end auto-answers with a quick "Anything else I can help with?".`
      : surface === "comment"
        ? `You are replying to a PUBLIC comment on a post. Keep it short and friendly; remember anyone can see it.`
        : `You are replying to a private message (DM/text) from a customer.`;
  return [
    `You ARE ${p.name} — reply as the business, in first person ("we", "our"). Never say you're an AI, a bot, or an assistant.`,
    `Voice: ${p.persona}`,
    p.services.length ? `Services we offer:\n${p.services.map((s) => `- ${s}`).join("\n")}` : "",
    p.hours ? `Hours: ${p.hours}` : "",
    faq ? `What we know (your ONLY source of facts — never invent beyond this):\n\n${faq}` : "",
    examples
      ? `EXACTLY how we sound — mirror this tone, length, rhythm, and word choice (these are real; copy the vibe, not the facts):\n\n${examples}`
      : "",
    channel,
    ``,
    `HOW TO SOUND HUMAN:`,
    `- Read what the customer actually wrote and respond to THAT, specifically. Reference their exact situation/words, not a generic template.`,
    `- Write like a real person typing back — warm, natural, a little casual. Contractions ("we'll", "that's"). No corporate or robotic phrasing, no "Thank you for reaching out", no form-letter vibe.`,
    `- Match their energy and length. If they sent one line, send one or two. Don't over-explain.`,
    `- Vary your wording between messages; never reuse a canned sentence.`,
    `- Only state facts that are in "What we know" above. If you're not sure, escalate instead of guessing.`,
    ``,
    `DECIDE between two actions:`,
    `1. "auto_reply" — the message is a general question you can answer accurately from what we know, AND it is NOT an escalation trigger below. Write the actual human reply in "reply".`,
    `2. "escalate" — the message needs a real person (see triggers below). In "reply", write a short, genuine holding message that (a) acknowledges their specific question and (b) tells them a team member will follow up personally — e.g. for pricing: "Happy to get you a price on that — let me grab the details and someone from our team will message you right back." Do NOT answer the question yourself. The owner sees "reason".`,
    ``,
    `ALWAYS escalate — never answer these yourself — when the message involves:`,
    escalate,
    `Also escalate anything ambiguous, emotionally charged, a complaint, or that you're not confident about.`,
    `CRITICAL: never quote, estimate, or hint at a price or a quote. Anything about cost/pricing/quotes/estimates is ALWAYS an escalation.`,
    ``,
    crossSell
      ? `CROSS-SELL — we also refer work to sister companies. If the customer's message hints at any of these, set "crossSellPartner" to the partner name and "crossSellReason" to what they said. Otherwise set both to "". Always still handle their actual question normally (answer or escalate) — cross-sell is a separate flag, never instead of helping them.\n${crossSell}`
      : `Set "crossSellPartner" and "crossSellReason" to "".`,
    `Set "confidence" (0-1) = how sure you are the auto_reply is correct and safe. "category" = a short tag (e.g. "fall_cleanup", "service_area", "pricing", "complaint"). ${emojiRule}`,
    p.signoff ? `If auto-replying, you may end with: "${p.signoff}"` : "",
  ]
    .filter(Boolean)
    .join("\n");
}

/** Safe fallback when the model call or parsing fails — never auto-send junk. */
function failSafe(reason: string): Decision {
  return {
    action: "escalate",
    category: "error",
    reply: "Thanks for reaching out — someone will get back to you shortly!",
    confidence: 0,
    reason,
    crossSellPartner: "",
    crossSellReason: "",
  };
}

/**
 * Open models don't honor strict JSON schemas reliably: strip code fences, grab the
 * outermost {...}, and coerce/validate every field. Anything unusable → null.
 */
function parseDecision(raw: string): Decision | null {
  const start = raw.indexOf("{");
  const end = raw.lastIndexOf("}");
  if (start === -1 || end <= start) return null;
  try {
    const d = JSON.parse(raw.slice(start, end + 1)) as Partial<Decision>;
    if (d.action !== "auto_reply" && d.action !== "escalate") return null;
    if (typeof d.reply !== "string" || !d.reply.trim()) return null;
    return {
      action: d.action,
      category: typeof d.category === "string" ? d.category : "general",
      reply: d.reply,
      confidence: typeof d.confidence === "number" ? d.confidence : 0,
      reason: typeof d.reason === "string" ? d.reason : "",
      crossSellPartner: typeof d.crossSellPartner === "string" ? d.crossSellPartner : "",
      crossSellReason: typeof d.crossSellReason === "string" ? d.crossSellReason : "",
    };
  } catch {
    return null;
  }
}

const JSON_INSTRUCTION =
  `\nRespond with ONLY a single JSON object — no prose, no markdown fences — shaped exactly like:\n` +
  `{"action":"auto_reply"|"escalate","category":"...","reply":"...","confidence":0.0,"reason":"...","crossSellPartner":"...","crossSellReason":"..."}`;

/** Free brain: Cloudflare Workers AI (open model, prompt-enforced JSON). */
async function decideWorkersAi(env: Env, it: Interaction, system: string): Promise<Decision> {
  if (!env.AI) return failSafe("Workers AI binding missing (set [ai] binding in wrangler.toml)");
  const model = env.WORKERS_AI_MODEL || "@cf/meta/llama-3.3-70b-instruct-fp8-fast";
  const result = (await env.AI.run(model as Parameters<Ai["run"]>[0], {
    messages: [
      { role: "system", content: system + JSON_INSTRUCTION },
      {
        role: "user",
        content:
          `Platform: ${it.platform} (${it.surface})\n` +
          `From: ${it.username ?? it.senderId}\n` +
          `Message: ${it.text}`,
      },
    ],
    max_tokens: 800,
  })) as { response?: string };
  const parsed = parseDecision(result.response ?? "");
  return parsed ?? failSafe("Workers AI returned unparseable output");
}

/** Paid brain: Claude with strict structured outputs. */
async function decideClaude(env: Env, it: Interaction, system: string): Promise<Decision> {
  const client = new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });
  // `output_config` (structured outputs + effort) is newer than the SDK's static
  // types but is forwarded on the wire; intersect the type so the call typechecks.
  const params: Anthropic.MessageCreateParamsNonStreaming & { output_config: unknown } = {
    model: env.CLAUDE_MODEL || "claude-opus-4-8",
    max_tokens: 1024,
    // Cache the per-business system prompt across messages from the same page.
    system: [{ type: "text", text: system, cache_control: { type: "ephemeral" } }],
    output_config: {
      effort: (env.CLAUDE_EFFORT as "low" | "medium" | "high") || "low",
      format: { type: "json_schema", schema: DECISION_SCHEMA },
    },
    messages: [
      {
        role: "user",
        content:
          `Platform: ${it.platform} (${it.surface})\n` +
          `From: ${it.username ?? it.senderId}\n` +
          `Message: ${it.text}`,
      },
    ],
  };
  const resp = await client.messages.create(params);
  const block = resp.content.find((b) => b.type === "text");
  const raw = block && block.type === "text" ? block.text : "{}";
  return JSON.parse(raw) as Decision;
}

/**
 * Deterministic pricing backstop (model-independent): if the customer's message
 * plainly asks about money, it MUST escalate — even if the model said auto_reply.
 * This guards against weaker free models slipping on the no-pricing rule.
 */
const PRICING_RE =
  /\b(price|prices|pricing|cost|costs|quote|quotes|estimate|estimates|rate|rates|fee|fees|charge|charges|how much|ball\s?park|budget)\b|\$\s?\d/i;

/**
 * Classify the interaction and draft a reply with the configured AI provider
 * (free Workers AI by default; Claude when AI_PROVIDER="claude"). Falls back to a
 * safe escalation on any error so we never auto-send junk.
 */
export async function decide(env: Env, it: Interaction): Promise<Decision> {
  const profile = getProfile(it.pageId);
  const system = systemPrompt(profile, it.surface);

  try {
    const parsed =
      env.AI_PROVIDER === "claude"
        ? await decideClaude(env, it, system)
        : await decideWorkersAi(env, it, system);

    // Confidence floor: even if the model said auto_reply, escalate if it's shaky.
    const floor = Number(env.MIN_AUTOREPLY_CONFIDENCE || "0.72");
    if (parsed.action === "auto_reply" && parsed.confidence < floor) {
      parsed.action = "escalate";
      parsed.reason = `Below confidence floor (${parsed.confidence} < ${floor}): ${parsed.reason}`;
    }

    // Hard pricing backstop: money talk always goes to a human, no exceptions.
    if (parsed.action === "auto_reply" && PRICING_RE.test(it.text)) {
      parsed.action = "escalate";
      parsed.category = "pricing";
      parsed.reply =
        "Great question — every project's a little different, so let me grab a few details and someone from our team will get right back to you. Estimates are free!";
      parsed.reason = `Pricing keyword backstop triggered (model tried to auto-reply): ${parsed.reason}`;
    }
    return parsed;
  } catch (err) {
    return failSafe(`AI call failed: ${(err as Error).message}`);
  }
}
