export interface Env {
  STATE: KVNamespace;

  // vars
  CLAUDE_MODEL: string;
  CLAUDE_EFFORT: string;
  MIN_AUTOREPLY_CONFIDENCE: string;

  // secrets
  META_APP_SECRET: string;
  META_VERIFY_TOKEN: string;
  META_PAGE_TOKEN?: string;
  META_PAGE_TOKENS?: string; // JSON: { [pageId]: token }
  ANTHROPIC_API_KEY: string;
  ESCALATION_WEBHOOK_URL?: string;

  // Twilio (optional — needed for phone calls, inbound SMS, and owner-notify texts)
  TWILIO_AUTH_TOKEN?: string;
  TWILIO_ACCOUNT_SID?: string; // required to SEND texts (owner notifications / SMS replies)
  // Optional override if a proxy rewrites the public URL Twilio signs against.
  PUBLIC_BASE_URL?: string;

  // Email alerts (optional — needed to email the owner on escalations). Uses Resend.
  RESEND_API_KEY?: string;
  ALERT_EMAIL_FROM?: string; // verified sender, e.g. "alerts@yourdomain.com"

  // Free phone-push alert (no Twilio). An ntfy.sh topic URL (or any endpoint that
  // accepts a plain-text POST). Lands on your phone like a text. e.g.
  // https://ntfy.sh/hp-landscaping-9f2c1   (pick a long, hard-to-guess name)
  PUSH_URL?: string;
}

export type Platform = "facebook" | "instagram" | "phone" | "sms";
export type Surface = "dm" | "comment" | "call" | "text";

/** A normalized inbound interaction, regardless of platform/surface. */
export interface Interaction {
  id: string; // unique event id (used for dedup)
  platform: Platform;
  surface: Surface;
  pageId: string; // the page/IG account that received it
  senderId: string; // PSID (DM) or commenter id
  text: string;
  /** For comments: the comment id we reply under. For DMs: undefined. */
  commentId?: string;
  username?: string;
}

/** Structured decision returned by Claude for one interaction. */
export interface Decision {
  action: "auto_reply" | "escalate";
  category: string;
  reply: string;
  confidence: number;
  reason: string;
  /** Cross-sell: the partner business this is a lead for ("" if none). */
  crossSellPartner: string;
  /** What the customer said that signals the cross-sell lead ("" if none). */
  crossSellReason: string;
}
