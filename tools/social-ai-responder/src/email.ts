import type { Env } from "./types";

/**
 * Send an email via Resend (https://resend.com). Returns true on success, false if
 * email isn't configured (RESEND_API_KEY / ALERT_EMAIL_FROM unset) or no recipients.
 */
export async function sendEmail(
  env: Env,
  to: string[],
  subject: string,
  text: string,
): Promise<boolean> {
  if (!env.RESEND_API_KEY || !env.ALERT_EMAIL_FROM || to.length === 0) return false;
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ from: env.ALERT_EMAIL_FROM, to, subject, text }),
  });
  return res.ok;
}
