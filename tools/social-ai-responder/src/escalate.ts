import type { Decision, Env, Interaction } from "./types";
import { getProfile, type BusinessProfile } from "./knowledge";
import { sendSms } from "./twilio";
import { sendEmail } from "./email";

export interface EscalationRecord {
  at: string;
  it: Interaction;
  decision: Decision;
}

const asList = (v?: string | string[]): string[] => (v ? (Array.isArray(v) ? v : [v]) : []);

/** Fan an alert out to every configured human channel (text, email, phone push, webhook). */
async function alertHumans(
  env: Env,
  profile: BusinessProfile,
  subject: string,
  body: string,
): Promise<void> {
  for (const cell of asList(profile.notify?.ownerSms)) {
    try {
      await sendSms(env, profile.twilioNumber, cell, body);
    } catch {
      /* non-fatal */
    }
  }

  const emails = asList(profile.notify?.ownerEmail);
  if (emails.length) {
    try {
      await sendEmail(env, emails, subject, body);
    } catch {
      /* non-fatal */
    }
  }

  if (env.PUSH_URL) {
    try {
      await fetch(env.PUSH_URL, {
        method: "POST",
        headers: { Title: subject, Priority: "high" },
        body,
      });
    } catch {
      /* non-fatal */
    }
  }

  if (env.ESCALATION_WEBHOOK_URL) {
    try {
      await fetch(env.ESCALATION_WEBHOOK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: `🔔 ${subject}\n${body}` }),
      });
    } catch {
      /* non-fatal */
    }
  }
}

/** Persist an escalation to KV and alert humans so a PERSON takes over. */
export async function escalate(env: Env, it: Interaction, decision: Decision): Promise<void> {
  const record: EscalationRecord = { at: new Date().toISOString(), it, decision };
  const profile = getProfile(it.pageId);
  const channel = `${it.platform}/${it.surface}`;

  await env.STATE.put(`esc:${Date.now()}:${it.id}`, JSON.stringify(record), {
    expirationTtl: 60 * 60 * 24 * 30,
  });

  const body =
    `${profile.name}: a customer needs you (${decision.category}, via ${channel}).\n` +
    `From: ${it.username ?? it.senderId}\n` +
    `They said: "${it.text}"\n` +
    `Reply to them directly on ${it.platform} to take it over.`;
  await alertHumans(env, profile, `New ${decision.category} inquiry — ${profile.name}`, body);
}

/**
 * A cross-sell lead: this conversation (for one business) signals an opportunity for a
 * sister business. Logged separately and alerted so the team can follow up.
 */
export async function logCrossSell(
  env: Env,
  it: Interaction,
  partner: string,
  reason: string,
): Promise<void> {
  const profile = getProfile(it.pageId);
  const record = { at: new Date().toISOString(), partner, reason, it };

  await env.STATE.put(`lead:${Date.now()}:${it.id}`, JSON.stringify(record), {
    expirationTtl: 60 * 60 * 24 * 60,
  });

  const body =
    `Possible ${partner} lead from a ${profile.name} ${it.platform} chat.\n` +
    `Customer: ${it.username ?? it.senderId}\n` +
    `They said: "${it.text}"\n` +
    `Signal: ${reason}\n` +
    `Someone from ${partner} may want to reach out.`;
  await alertHumans(env, profile, `Possible ${partner} lead — via ${profile.name}`, body);
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

/** Read the cross-sell lead queue (newest first). */
export async function listLeads(env: Env): Promise<unknown[]> {
  const list = await env.STATE.list({ prefix: "lead:" });
  const records: unknown[] = [];
  for (const k of list.keys) {
    const v = await env.STATE.get(k.name);
    if (v) records.push(JSON.parse(v));
  }
  return records;
}
