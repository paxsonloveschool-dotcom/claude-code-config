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
    /** Personal cell(s) to TEXT on every escalation. One number or several (a team). */
    ownerSms?: string | string[];
    /** Email(s) to alert on every escalation. One address or several (a team). */
    ownerEmail?: string | string[];
  };
  /** This business's Twilio number (E.164) — the "From" for outgoing SMS we send. */
  twilioNumber?: string;
  /**
   * Cross-sell: sister businesses to flag leads for. If a customer's message hits any
   * of a partner's `signals`, the team gets a "possible <partner> lead" alert — the
   * customer's own question is still answered/escalated normally.
   */
  crossSell?: { partner: string; signals: string[] }[];
}

export const BUSINESSES: Record<string, BusinessProfile> = {
  // ----------------------------------------------------------------------------
  // Replace the key with your real Page ID. Duplicate the block per business.
  // ----------------------------------------------------------------------------
  "REPLACE_WITH_PAGE_ID": {
    name: "HP Landscaping",
    persona:
      "Luxury landscape design & build company in College Station, TX, founded in 2015 by a Texas A&M grad. Friendly, down-to-earth Texas warmth with the polish of a high-end design firm. Proud of craftsmanship; never salesy or stiff.",
    services: [
      "Custom landscape design (in-house 3D design, CAD layouts, master planning)",
      "Custom pools integrated with landscaping and outdoor living",
      "Outdoor kitchens (grills, sinks, storage, stone finishes)",
      "Hardscaping — pavers, travertine, porcelain, natural stone patios & walkways",
      "Structural & decorative concrete (patios, walkways)",
      "Retaining walls",
      "Decks (elevated or ground-level) and pergolas/shade structures (wood or steel)",
      "Fire features (fire pits, fireplaces)",
      "Fencing (privacy & perimeter)",
      "Drainage systems and zoned sprinkler/drip irrigation",
      "Synthetic grass and sod installation",
      "Tree planting and tree services",
      "Low-voltage LED landscape lighting",
      "Ranch improvement — land clearing, underbrush/invasive removal, stump removal, land reshaping for drainage and access",
      "Landscape maintenance",
    ],
    hours: "Mon–Sat 7am–5pm. Closed Sundays. Phone: (979) 701-2229.",
    faq: [
      {
        q: "What areas do you service?",
        a: "We're based in College Station at 14801 S Dowling Rd and serve Bryan, Aggieland, and the whole Brazos Valley — plus the Greater Houston area.",
      },
      {
        q: "Do you offer free estimates?",
        a: "We do — estimates and consultations are free. Share what you have in mind and we'll set one up.",
      },
      {
        q: "Do you do design in-house?",
        a: "Yes — full in-house design with 3D renderings, CAD layouts, and master planning. We also work alongside architects or builders when needed.",
      },
      {
        q: "How long does a project take?",
        a: "Most large projects wrap in about 4–10 weeks, weather permitting. We give a clear timeline up front and weekly updates throughout.",
      },
      {
        q: "Do you offer a warranty?",
        a: "Yes — a 1-year craftsmanship warranty on all structural work, with extended warranties available on select systems and materials.",
      },
      {
        q: "Do you offer financing?",
        a: "We do — flexible project financing up to $1.5M with options from 0%–15%, a simple application, and fast approvals.",
      },
      {
        q: "How will I know what's happening during my project?",
        a: "You'll have a dedicated project manager with daily text and photo updates plus milestone check-ins. You're never left wondering.",
      },
      {
        q: "Do you handle the whole build?",
        a: "Yes — we're a true design & build company. We manage everything from demolition to the final landscape lighting.",
      },
      {
        q: "Do you do ranch work?",
        a: "We do — land clearing, underbrush and invasive removal, stump removal, and reshaping land for drainage and access across Texas ranch properties.",
      },
    ],
    // Voice tuning: friendly Texas warmth, design-build confidence, no emojis.
    styleExamples: [
      {
        customer: "do y'all do outdoor kitchens?",
        reply:
          "We sure do — outdoor kitchens are one of our favorites. Grills, sinks, storage, stone finishes, the works. What kind of space are you working with?",
      },
      {
        customer: "what areas do you cover?",
        reply:
          "We're based in College Station and cover Bryan, Aggieland, and the Brazos Valley — plus the Greater Houston area. Where's your place?",
      },
      {
        customer: "how long would a full backyard remodel take?",
        reply:
          "Most of our bigger projects run about 4 to 10 weeks depending on scope and weather. We map out the timeline with you up front and send weekly updates the whole way.",
      },
      {
        customer: "do you guys design it too or do I need my own plans?",
        reply:
          "We handle design in-house — 3D renderings and CAD layouts so you can see it before we build it. If you've already got an architect, we work with them too.",
      },
      {
        customer: "what would a pool and patio run me?",
        reply:
          "Great question — every project's different, so let me grab a few details and someone from our team will reach out personally. Estimates are free. What's your location and roughly what are you envisioning?",
      },
      {
        customer: "do you do regular maintenance or just big projects?",
        reply: "Both! We do full design-and-build projects and ongoing landscape maintenance. What do you need taken care of?",
      },
    ],
    useEmojis: false,
    // Pricing, complaints, scheduling-specific commitments, and contracts go to a human.
    escalateWhen: [
      "ANY mention of price, cost, quote, estimate, rate, fee, 'how much', 'ballpark', or 'what do you charge' — always hand these to a human, never answer (you may mention estimates are free while handing off)",
      "complaint or dissatisfaction about prior work",
      "requesting a specific appointment date/time commitment",
      "billing, refunds, financing applications, or payment disputes",
      "anything legal, contracts, or insurance claims",
      "an urgent / same-day request",
    ],
    signoff: "",
    voice: {
      greeting:
        "Thanks for calling HP Landscaping in College Station! I can help with questions about our design and build services. How can I help you today?",
      // transferNumber: "+19797012229", // main line / owner's cell for warm transfers
    },
    // When a pricing/quote/complaint comes in, alert a HUMAN so they reply (not the AI).
    // Both can be a single value or a list for a small team, e.g. ["+1...", "+1..."].
    notify: {
      // ownerSms: "+15551234567",                 // personal cell(s) to text
      // ownerEmail: "owner@hplandscaping.com",    // email(s) to alert
    },
    // twilioNumber: "+15550000000", // the Twilio number customers text/call
    // Flag leads for the sister restoration company when these come up.
    crossSell: [
      {
        partner: "Restore",
        signals: [
          "water damage",
          "flooding or flooded",
          "mold",
          "storm or wind damage",
          "fire or smoke damage",
          "burst pipe or leak damage",
          "basement water",
        ],
      },
    ],
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
