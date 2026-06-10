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
}

export type Platform = "facebook" | "instagram";
export type Surface = "dm" | "comment";

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
}
