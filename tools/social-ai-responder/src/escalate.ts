import type { Decision, Env, Interaction } from "./types";

export interface EscalationRecord {
  at: string;
  it: Interaction;
  decision: Decision;
}

/** Persist an escalation to KV and (optionally) push it to the owner. */
export async function escalate(env: Env, it: Interaction, decision: Decision): Promise<void> {
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

/** Read the escalation queue (newest first). */
export async function listEscalations(env: Env): Promise<EscalationRecord[]> {
  const list = await env.STATE.list({ prefix: "esc:" });
  const records: EscalationRecord[] = [];
  for (const k of list.keys) {
    const v = await env.STATE.get(k.name);
    if (v) records.push(JSON.parse(v) as EscalationRecord);
  }
  return records.sort((a, b) => b.at.localeCompare(a.at));
}
