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
  },
  required: ["action", "category", "reply", "confidence", "reason"],
} as const;

function systemPrompt(p: BusinessProfile, surface: "dm" | "comment" | "call"): string {
  const faq = p.faq.map((f) => `Q: ${f.q}\nA: ${f.a}`).join("\n\n");
  const escalate = p.escalateWhen.map((e) => `- ${e}`).join("\n");
  const channel =
    surface === "call"
      ? `You are answering a LIVE PHONE CALL. Your reply will be read aloud by text-to-speech, so: speak in plain spoken sentences, no markdown, no links, no emojis, and keep it to 1-2 short sentences. End auto-answers with a brief question like "Anything else I can help with?".`
      : `You are answering a public comment or a private message from a potential customer.`;
  return [
    `You are the assistant for ${p.name}.`,
    `Voice: ${p.persona}`,
    p.services.length ? `Services offered:\n${p.services.map((s) => `- ${s}`).join("\n")}` : "",
    p.hours ? `Hours: ${p.hours}` : "",
    faq ? `Known answers (your source of truth — do not invent facts beyond these):\n\n${faq}` : "",
    channel,
    ``,
    `DECIDE between two actions:`,
    `1. "auto_reply" — ONLY when the message is a general question you can answer accurately from the known answers/services/hours above, AND it is NOT one of the escalation triggers below. Write a short, on-brand reply (1-3 sentences). Never quote a price, never commit to a specific date, never invent details.`,
    `2. "escalate" — when the message needs a human. Still write a brief, friendly holding reply (e.g. "Great question — let me check and get right back to you!") in the "reply" field; the human will follow up. The owner will see your "reason".`,
    ``,
    `ALWAYS escalate when the message involves:`,
    escalate,
    `Also escalate anything ambiguous, emotionally charged, or that you are not confident about.`,
    ``,
    `Set "confidence" (0-1) = how sure you are the auto_reply is correct and safe. "category" = a short tag (e.g. "fall_cleanup", "service_area", "pricing", "complaint"). Keep replies free of emojis unless the customer used them first.`,
    p.signoff ? `If auto-replying, you may end with: "${p.signoff}"` : "",
  ]
    .filter(Boolean)
    .join("\n");
}

/**
 * Single Claude call: classify the interaction and draft a reply. Returns a typed
 * Decision. Falls back to a safe escalation on any error so we never auto-send junk.
 */
export async function decide(env: Env, it: Interaction): Promise<Decision> {
  const profile = getProfile(it.pageId);
  const client = new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });

  try {
    // `output_config` (structured outputs + effort) is newer than the SDK's static
    // types but is forwarded on the wire; intersect the type so the call typechecks.
    const params: Anthropic.MessageCreateParamsNonStreaming & { output_config: unknown } = {
      model: env.CLAUDE_MODEL || "claude-opus-4-8",
      max_tokens: 1024,
      // Cache the per-business system prompt across messages from the same page.
      system: [
        { type: "text", text: systemPrompt(profile, it.surface), cache_control: { type: "ephemeral" } },
      ],
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
    const parsed = JSON.parse(raw) as Decision;

    // Confidence floor: even if the model said auto_reply, escalate if it's shaky.
    const floor = Number(env.MIN_AUTOREPLY_CONFIDENCE || "0.72");
    if (parsed.action === "auto_reply" && parsed.confidence < floor) {
      parsed.action = "escalate";
      parsed.reason = `Below confidence floor (${parsed.confidence} < ${floor}): ${parsed.reason}`;
    }
    return parsed;
  } catch (err) {
    return {
      action: "escalate",
      category: "error",
      reply: "Thanks for reaching out — someone will get back to you shortly!",
      confidence: 0,
      reason: `Claude call failed: ${(err as Error).message}`,
    };
  }
}
