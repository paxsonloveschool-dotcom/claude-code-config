import type { Env, Interaction } from "./types";

const GRAPH = "https://graph.facebook.com/v21.0";

/** Resolve the page access token for a given page id. */
function tokenFor(env: Env, pageId: string): string | undefined {
  if (env.META_PAGE_TOKENS) {
    try {
      const map = JSON.parse(env.META_PAGE_TOKENS) as Record<string, string>;
      if (map[pageId]) return map[pageId];
    } catch {
      /* fall through to single token */
    }
  }
  return env.META_PAGE_TOKEN;
}

/** GET webhook verification handshake. Returns the challenge or null. */
export function verifySubscription(url: URL, env: Env): string | null {
  const mode = url.searchParams.get("hub.mode");
  const token = url.searchParams.get("hub.verify_token");
  const challenge = url.searchParams.get("hub.challenge");
  if (mode === "subscribe" && token === env.META_VERIFY_TOKEN && challenge) {
    return challenge;
  }
  return null;
}

/** Verify the X-Hub-Signature-256 HMAC over the raw body using the app secret. */
export async function verifySignature(
  rawBody: string,
  signatureHeader: string | null,
  appSecret: string,
): Promise<boolean> {
  if (!signatureHeader?.startsWith("sha256=")) return false;
  const expectedHex = signatureHeader.slice("sha256=".length);

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(appSecret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sigBuf = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(rawBody));
  const actualHex = [...new Uint8Array(sigBuf)].map((b) => b.toString(16).padStart(2, "0")).join("");

  // constant-time-ish compare
  if (actualHex.length !== expectedHex.length) return false;
  let diff = 0;
  for (let i = 0; i < actualHex.length; i++) diff |= actualHex.charCodeAt(i) ^ expectedHex.charCodeAt(i);
  return diff === 0;
}

/**
 * Normalize a Meta webhook body into a flat list of Interactions across both
 * Messenger/IG DMs (`messaging`) and Page/IG comments (`changes`).
 */
export function parseWebhook(body: any): Interaction[] {
  const out: Interaction[] = [];
  const platform = body?.object === "instagram" ? "instagram" : "facebook";

  for (const entry of body?.entry ?? []) {
    const pageId = String(entry?.id ?? "");

    // --- DMs (Messenger + Instagram Direct) ---
    for (const m of entry?.messaging ?? []) {
      const text: string | undefined = m?.message?.text;
      const mid: string | undefined = m?.message?.mid;
      // Ignore echoes (our own outgoing messages) and non-text events.
      if (m?.message?.is_echo || !text || !mid) continue;
      out.push({
        id: mid,
        platform,
        surface: "dm",
        pageId,
        senderId: String(m?.sender?.id ?? ""),
        text,
      });
    }

    // --- Comments (Page feed + Instagram comments) ---
    for (const change of entry?.changes ?? []) {
      const field: string = change?.field ?? "";
      const v = change?.value ?? {};
      const isComment =
        (field === "feed" && v?.item === "comment" && v?.verb === "add") ||
        field === "comments";
      if (!isComment) continue;

      const commentId: string | undefined = v?.comment_id ?? v?.id;
      const text: string | undefined = v?.message ?? v?.text;
      const fromId = String(v?.from?.id ?? v?.sender_id ?? "");

      if (!commentId || !text) continue;
      // Skip comments authored by the page itself.
      if (fromId && fromId === pageId) continue;

      out.push({
        id: commentId,
        platform,
        surface: "comment",
        pageId,
        senderId: fromId,
        commentId,
        text,
        username: v?.from?.username ?? v?.from?.name,
      });
    }
  }
  return out;
}

/** Send a private message (DM reply) to a user via the Send API. */
export async function sendDirectMessage(env: Env, it: Interaction, text: string): Promise<void> {
  const token = tokenFor(env, it.pageId);
  if (!token) throw new Error(`No page token for ${it.pageId}`);
  await graphPost(`${GRAPH}/me/messages?access_token=${token}`, {
    recipient: { id: it.senderId },
    message: { text },
    messaging_type: "RESPONSE",
  });
}

/** Reply publicly under a comment. */
export async function replyToComment(env: Env, it: Interaction, text: string): Promise<void> {
  const token = tokenFor(env, it.pageId);
  if (!token) throw new Error(`No page token for ${it.pageId}`);
  await graphPost(`${GRAPH}/${it.commentId}/comments?access_token=${token}`, { message: text });
}

/**
 * Send a PRIVATE reply (DM) to the author of a comment. Meta allows exactly one
 * private reply per comment, within a limited window after it's posted. Works for
 * Facebook Page comments and Instagram comments.
 */
export async function sendPrivateReply(env: Env, it: Interaction, text: string): Promise<void> {
  const token = tokenFor(env, it.pageId);
  if (!token) throw new Error(`No page token for ${it.pageId}`);
  await graphPost(`${GRAPH}/${it.commentId}/private_replies?access_token=${token}`, { message: text });
}

/**
 * Deliver a reply to the right place.
 * - DMs/texts → straight back to the sender.
 * - A comment with a BASIC question (auto-reply) → answered publicly under the comment.
 * - A comment that's personal — pricing, quotes, "can you do mine", more detail
 *   (escalated) → answered with a PRIVATE DM only, never publicly. If Meta's
 *   private-reply window has closed, we fall back to a public acknowledgement so the
 *   person isn't left hanging.
 */
export async function deliverReply(
  env: Env,
  it: Interaction,
  text: string,
  escalated: boolean,
): Promise<void> {
  if (it.surface !== "comment") return sendDirectMessage(env, it, text);

  if (!escalated) return replyToComment(env, it, text);

  try {
    await sendPrivateReply(env, it, text);
  } catch {
    await replyToComment(env, it, text);
  }
}

async function graphPost(url: string, payload: unknown): Promise<void> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`Graph API ${res.status}: ${txt}`);
  }
}
