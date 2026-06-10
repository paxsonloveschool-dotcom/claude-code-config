/**
 * Per-business knowledge that drives auto-replies. Keyed by the Meta Page ID (and/or
 * Instagram account id) that received the message. Find your Page ID in Meta Business
 * Suite > Settings, or in the webhook payload (`entry[].id`).
 *
 * Edit `services`, `faq`, `hours`, and `escalateWhen` per business. The bot will only
 * auto-answer things it's confident about and that aren't in `escalateWhen`; everything
 * else is routed to you.
 */
export interface BusinessProfile {
  name: string;
  /** One or two sentences describing the business and its voice. */
  persona: string;
  services: string[];
  hours: string;
  /** Plain Q→A pairs. The model uses these as the source of truth for FAQ answers. */
  faq: { q: string; a: string }[];
  /** Topics that must ALWAYS be escalated to a human, never auto-answered. */
  escalateWhen: string[];
  /** Optional closing line appended to auto-replies (e.g. a booking link). */
  signoff?: string;
}

export const BUSINESSES: Record<string, BusinessProfile> = {
  // ----------------------------------------------------------------------------
  // Replace the key with your real Page ID. Duplicate the block per business.
  // ----------------------------------------------------------------------------
  "REPLACE_WITH_PAGE_ID": {
    name: "HP Landscaping",
    persona:
      "Friendly, local, no-nonsense landscaping company. Warm but concise. Talks like a neighbor, not a corporation.",
    services: [
      "Lawn mowing & maintenance",
      "Spring & fall cleanups",
      "Mulching and bed edging",
      "Shrub trimming",
      "Leaf removal",
      "Snow removal (seasonal)",
    ],
    hours: "Mon–Sat 7am–6pm. Closed Sundays.",
    faq: [
      {
        q: "What areas do you service?",
        a: "We cover the local metro area and surrounding suburbs. If you share your town we can confirm.",
      },
      {
        q: "Do you do fall cleanups?",
        a: "Yes — fall cleanups include leaf removal, bed cleanup, and a final mow. We book these from September through November.",
      },
      {
        q: "Are you insured?",
        a: "Yes, we're fully licensed and insured.",
      },
      {
        q: "How do I get on the schedule?",
        a: "Send your address and the service you want and we'll get you a slot — usually within a few days.",
      },
    ],
    // Pricing, complaints, scheduling-specific commitments, and contracts go to a human.
    escalateWhen: [
      "asking for a specific price, quote, or estimate",
      "complaint or dissatisfaction about prior work",
      "requesting a specific appointment date/time commitment",
      "billing, refunds, or payment disputes",
      "anything legal, contracts, or insurance claims",
      "an urgent / same-day request",
    ],
    signoff: "",
  },
};

/** Fallback used when a Page ID isn't in BUSINESSES (so the bot never crashes). */
export const DEFAULT_PROFILE: BusinessProfile = {
  name: "our business",
  persona: "Helpful, friendly, and concise.",
  services: [],
  hours: "",
  faq: [],
  escalateWhen: [
    "asking for a specific price, quote, or estimate",
    "complaints",
    "scheduling a specific appointment",
    "billing or payments",
  ],
  signoff: "",
};

export function getProfile(pageId: string): BusinessProfile {
  return BUSINESSES[pageId] ?? DEFAULT_PROFILE;
}
