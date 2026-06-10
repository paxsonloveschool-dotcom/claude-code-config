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
  /**
   * Voice tuning: real examples of how YOU reply. The model mirrors the tone,
   * length, and phrasing of these — the single most effective way to make replies
   * sound like you. 3-6 pairs is plenty.
   */
  styleExamples?: { customer: string; reply: string }[];
  /** Light emoji use in replies? Default false (only mirror the customer's emojis). */
  useEmojis?: boolean;
  /** Optional closing line appended to auto-replies (e.g. a booking link). */
  signoff?: string;
  /** Phase 2: phone-call settings. Omit to disable voice for this business. */
  voice?: {
    /** Spoken when the call connects. */
    greeting: string;
    /** E.164 number to warm-transfer escalations to (e.g. "+15551234567"). */
    transferNumber?: string;
  };
  /** Where/how to alert a human when something escalates (pricing, complaints, etc). */
  notify?: {
    /** Owner's cell — gets a text on every escalation so a human can take over. */
    ownerSms?: string;
  };
  /** This business's Twilio number (E.164) — the "From" for outgoing SMS we send. */
  twilioNumber?: string;
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
    // Voice tuning — replace these with REAL examples of how you reply (see README).
    styleExamples: [
      {
        customer: "do you guys still have any openings for weekly mowing?",
        reply: "Hey! Yep, we've still got a few weekly spots open. Whereabouts are you?",
      },
      {
        customer: "are you insured?",
        reply: "We sure are — fully licensed and insured. Anything you're looking to get done?",
      },
    ],
    useEmojis: false,
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
    voice: {
      greeting:
        "Thanks for calling HP Landscaping! I'm the virtual assistant and can help with questions about our services. How can I help you today?",
      // transferNumber: "+15551234567", // owner's cell for warm transfers
    },
    // When a pricing/quote/complaint comes in, text the owner so a HUMAN replies.
    notify: {
      // ownerSms: "+15551234567", // <-- your cell; uncomment + set to get alerts
    },
    // twilioNumber: "+15550000000", // the Twilio number customers text/call
  },
};

/**
 * Maps a Twilio phone number (the "To" number a customer dialed or texted, E.164)
 * to the Page ID key in BUSINESSES above. Lets one Worker serve voice + SMS for
 * multiple businesses. Add one entry per Twilio number you buy.
 */
export const NUMBER_TO_PAGE: Record<string, string> = {
  "+15550000000": "REPLACE_WITH_PAGE_ID",
};

/** Resolve the business profile for an inbound Twilio call/text by its "To" number. */
export function getProfileByPhone(toNumber: string): { pageId: string; profile: BusinessProfile } {
  const pageId = NUMBER_TO_PAGE[toNumber] ?? "unknown";
  return { pageId, profile: getProfile(pageId) };
}

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
