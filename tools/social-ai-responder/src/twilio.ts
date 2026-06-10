import type { Env } from "./types";

/** Escape text for safe inclusion in TwiML XML. */
export function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/** Wrap inner TwiML in a <Response> and return as an XML HTTP response. */
export function twiml(inner: string): Response {
  const xml = `<?xml version="1.0" encoding="UTF-8"?><Response>${inner}</Response>`;
  return new Response(xml, { status: 200, headers: { "Content-Type": "text/xml" } });
}

/** Full URL Twilio signed against (honor a proxy override if configured). */
function signedUrl(request: Request, env: Env): string {
  const url = new URL(request.url);
  if (env.PUBLIC_BASE_URL) {
    return env.PUBLIC_BASE_URL.replace(/\/$/, "") + url.pathname + url.search;
  }
  return request.url;
}

/**
 * Verify Twilio's X-Twilio-Signature: HMAC-SHA1 of (url + sorted key+value pairs),
 * base64-encoded, keyed by the auth token. https://www.twilio.com/docs/usage/security
 */
async function verifyTwilio(
  url: string,
  params: Record<string, string>,
  signature: string | null,
  authToken: string,
): Promise<boolean> {
  if (!signature) return false;
  let data = url;
  for (const key of Object.keys(params).sort()) data += key + params[key];

  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(authToken),
    { name: "HMAC", hash: "SHA-1" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign("HMAC", cryptoKey, new TextEncoder().encode(data));
  const expected = btoa(String.fromCharCode(...new Uint8Array(mac)));

  if (expected.length !== signature.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= expected.charCodeAt(i) ^ signature.charCodeAt(i);
  return diff === 0;
}

/** Read a Twilio form-encoded POST body into a flat param map. */
async function formParams(request: Request): Promise<Record<string, string>> {
  const form = await request.formData();
  const out: Record<string, string> = {};
  for (const [k, v] of form.entries()) out[k] = typeof v === "string" ? v : "";
  return out;
}

/** Verify a Twilio webhook and return its parsed params. */
export async function authed(
  request: Request,
  env: Env,
): Promise<{ ok: boolean; params: Record<string, string> }> {
  const params = await formParams(request);
  if (!env.TWILIO_AUTH_TOKEN) return { ok: false, params };
  const ok = await verifyTwilio(
    signedUrl(request, env),
    params,
    request.headers.get("x-twilio-signature"),
    env.TWILIO_AUTH_TOKEN,
  );
  return { ok, params };
}

/**
 * Send an SMS via the Twilio REST API. Returns true on success. No-op (false) if
 * Twilio sending creds or the from/to numbers aren't configured.
 */
export async function sendSms(
  env: Env,
  from: string | undefined,
  to: string | undefined,
  body: string,
): Promise<boolean> {
  if (!env.TWILIO_ACCOUNT_SID || !env.TWILIO_AUTH_TOKEN || !from || !to) return false;
  const auth = btoa(`${env.TWILIO_ACCOUNT_SID}:${env.TWILIO_AUTH_TOKEN}`);
  const form = new URLSearchParams({ From: from, To: to, Body: body });
  const res = await fetch(
    `https://api.twilio.com/2010-04-01/Accounts/${env.TWILIO_ACCOUNT_SID}/Messages.json`,
    {
      method: "POST",
      headers: {
        Authorization: `Basic ${auth}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: form.toString(),
    },
  );
  return res.ok;
}
