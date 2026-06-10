import type { Decision, Env, Interaction } from "./types";
import { getProfile } from "./knowledge";
import { sendSms } from "./twilio";
import { sendEmail } from "./email";

export interface EscalationRecord {
  at: string;
  it: Interaction;
  decision: Decision;
}

const asList = (v?: string | string[]): string[] => (v ? (Array.isArray(v) ? v : [v]) : []);

/** Persist an escalation to KV and alert humans (owner texts + emails + optional webhook). */
export async function escalate(env: Env, it: Interaction, decision: Decision): Promise<void> {
  const record: EscalationRecord = { at: new Date().toISOString(), it, decision };
  const profile = getProfile(it.pageId);
  const channel = `${it.platform}/${it.surface}`;

  // 1) Persist to KV so the owner can review via /escalations.
  await env.STATE.put(`esc:${Date.now()}:${it.id}`, JSON.stringify(record), {
    expirationTtl: 60 * 60 * 24 * 30,
  });

  // 2) Alert humans so a PERSON takes over (pricing, quotes, complaints, ...).
  const alert =
    `${profile.name}: a customer needs you (${decision.category}, via ${channel}).\n` +
    `From: ${it.username ?? it.senderId}\n` +
    `They said: "${it.text}"\n` +
    `Reply to them directly on ${it.platform} to take it over.`;

  // 2a) Text every personal cell on the list.
  for (const cell of asList(profile.notify?.ownerSms)) {
    try {
      await sendSms(env, profile.twilioNumber, cell, alert);
    } catch {
      /* non-fatal: still logged + other channels */
    }
  }

  // 2b) Email every address on the list.
  const emails = asList(profile.notify?.ownerEmail);
  if (emails.length) {
    try {
      await sendEmail(env, emails, `New ${decision.category} inquiry — ${profile.name}`, alert);
    } catch {
      /* non-fatal */
    }
  }

  // 2c) Free phone-push alert (no Twilio) — e.g. an ntfy.sh topic. Lands like a text.
  if (env.PUSH_URL) {
    try {
      await fetch(env.PUSH_URL, {
        method: "POST",
        headers: { Title: `New ${decision.category} — ${profile.name}`, Priority: "high" },
        body: alert,
      });
    } catch {
      /* non-fatal */
    }
  }

  // 3) Optional push notification (Slack/Discord/email-relay webhook).
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
