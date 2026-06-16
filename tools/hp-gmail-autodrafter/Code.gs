/**
 * HP Landscaping — Gmail Auto-Drafter (Google Apps Script)
 * --------------------------------------------------------
 * Runs on Google's servers every 30 minutes, 8:00 AM – 7:00 PM Central.
 * For each NEW client/business email it:
 *   - drafts a reply in HP's voice (NEVER sends — creates a Gmail draft only)
 *   - labels the thread "📝 Email In Draft" + a per-client/company name label
 * Skips spam, marketing, automated notifications, bills/receipts, and personal mail.
 *
 * One-time setup: see SETUP.md. After adding your API key, run setup() once.
 */

// ---------- Config ----------
var TIMEZONE = 'America/Chicago';
var BUSINESS_START_HOUR = 8;    // 8 AM
var BUSINESS_END_HOUR   = 19;   // 7 PM (exclusive)
var DRAFT_LABEL = '📝 Email In Draft';
var CLAUDE_MODEL = 'claude-haiku-4-5-20251001'; // cheap + fast. Swap to 'claude-sonnet-4-6' for higher quality.
var MAX_THREADS_PER_RUN = 25;

// Senders we never draft for (automated / billing / marketing / personal notifications).
var SKIP_SENDER_PATTERNS = [
  'no-reply', 'noreply', 'notification', 'notifications', 'mailer-daemon', 'donotreply',
  'quickbooks', 'intuit', 'getjobber', 'planhub', 'capitalone', 'johndeere', 'chase',
  'paypal', 'rapidfinance', 'accounts.google', 'sc-noreply', 'googleads', 'business profile',
  'procoretech', 'texasmutual', 'mailchimp', 'sendgrid', 'e-email', 'mkt.intuit'
];

/** Run this ONCE after setting ANTHROPIC_API_KEY. Sets the start cutoff + installs the 30-min trigger. */
function setup() {
  var props = PropertiesService.getScriptProperties();
  if (!props.getProperty('ANTHROPIC_API_KEY')) {
    throw new Error('Add ANTHROPIC_API_KEY in Project Settings → Script Properties first, then run setup() again.');
  }
  // Only handle mail received from now on (never touches the existing backlog):
  props.setProperty('CUTOFF_EPOCH', String(Math.floor(Date.now() / 1000)));
  // Remove any existing trigger for this function, then create a fresh 30-min one:
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'runAutoDrafter') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('runAutoDrafter').timeBased().everyMinutes(30).create();
  Logger.log('Setup complete — auto-drafter installed, runs every 30 min (8 AM–7 PM Central).');
}

/** Main job — fired by the trigger every 30 minutes. */
function runAutoDrafter() {
  var hour = parseInt(Utilities.formatDate(new Date(), TIMEZONE, 'H'), 10);
  if (hour < BUSINESS_START_HOUR || hour >= BUSINESS_END_HOUR) return; // outside business hours: do nothing

  var props = PropertiesService.getScriptProperties();
  var apiKey = props.getProperty('ANTHROPIC_API_KEY');
  if (!apiKey) { Logger.log('No ANTHROPIC_API_KEY set.'); return; }
  var cutoff = props.getProperty('CUTOFF_EPOCH') || '0';

  var draftLabel = getOrCreateLabel(DRAFT_LABEL);
  var threads = GmailApp.search('in:inbox after:' + cutoff, 0, MAX_THREADS_PER_RUN);

  threads.forEach(function (thread) {
    try {
      if (threadHasLabel(thread, DRAFT_LABEL)) return;                 // already drafted
      var messages = thread.getMessages();
      var last = messages[messages.length - 1];
      var from = last.getFrom() || '';
      if (/higherpurposelandscaping@gmail\.com/i.test(from)) return;   // we sent the last message
      if (isSkippedSender(from)) return;                               // automated / marketing / spam

      var result = draftWithClaude(apiKey, from, last.getSubject(), last.getPlainBody());
      if (!result || !result.actionable || !result.body) return;       // Claude judged it non-actionable

      last.createDraftReply(result.body);                              // creates a DRAFT only — never sends
      thread.addLabel(draftLabel);
      var name = sanitizeLabelName(result.clientName || extractName(from));
      if (name) thread.addLabel(getOrCreateLabel(name));
    } catch (e) {
      Logger.log('Error on "' + thread.getFirstMessageSubject() + '": ' + e);
    }
  });
}

/** Calls the Claude API to classify + draft. Returns {actionable, clientName, body} or null. */
function draftWithClaude(apiKey, from, subject, body) {
  var system =
    'You draft email replies for HP Landscaping (Higher Purpose Landscaping), a landscaping & construction ' +
    'company in the Bryan/College Station, TX area. You write in the owner\'s real voice.\n\n' +
    'VOICE — short, warm, eager, Texas-friendly. Greet with the person\'s first name + "!" (e.g. "Hi Caleb!"); ' +
    'if no name is given, "Hi there!". One or two short paragraphs. NO bullet lists. NO placeholders or brackets. ' +
    'Acknowledge their request, answer briefly, and move it forward by asking for a detail or offering to swing ' +
    'by for a look/quote. Typical phrasings: "we\'d love to help!", "this is definitely something we can take ' +
    'care of for you", "When would be a good time for me to swing by?", "Let me know what works best for you!".\n\n' +
    'SIGNATURE — for residential/general clients, end EXACTLY with these five lines and NOTHING after (no website URL):\n' +
    'Thanks,\nThe HP Landscaping Team\nGeneral Communications, HP Landscaping\n979-701-2229 Mobile\nhigherpurposelandscaping@gmail.com\n\n' +
    'For commercial bid invites / banks / engineering firms, instead end with:\n' +
    'Thanks,\nPaxson Layne Cole Berkey\nDirector of Sales, HP Landscaping\n979-777-8851 Mobile\nhigherpurposelandscaping@gmail.com\n\n' +
    'CLASSIFY first. If the email is spam, marketing, an automated notification, a bill/receipt/estimate, or ' +
    'personal (i.e. NOT a real client question or business/work/quote inquiry), it is NOT actionable.\n\n' +
    'Reply with ONLY a JSON object — no markdown, no extra prose:\n' +
    '{"actionable": true|false, "clientName": "<best-guess person or company name>", "body": "<full reply incl. signature, or empty if not actionable>"}';

  var user = 'From: ' + from + '\nSubject: ' + subject + '\n\nBody:\n' + (body || '').slice(0, 4000);

  var resp = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', {
    method: 'post',
    contentType: 'application/json',
    headers: { 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' },
    payload: JSON.stringify({
      model: CLAUDE_MODEL,
      max_tokens: 700,
      system: system,
      messages: [{ role: 'user', content: user }]
    }),
    muteHttpExceptions: true
  });

  if (resp.getResponseCode() !== 200) {
    Logger.log('Claude API error ' + resp.getResponseCode() + ': ' + resp.getContentText());
    return null;
  }
  var data = JSON.parse(resp.getContentText());
  var text = (data.content && data.content[0] && data.content[0].text) ? data.content[0].text : '';
  return parseClaudeJson(text);
}

function parseClaudeJson(text) {
  try {
    var s = text.indexOf('{'), e = text.lastIndexOf('}');
    if (s < 0 || e < 0) return null;
    return JSON.parse(text.substring(s, e + 1));
  } catch (err) {
    Logger.log('JSON parse error: ' + err + ' | raw: ' + text);
    return null;
  }
}

// ---------- helpers ----------
function isSkippedSender(from) {
  var f = from.toLowerCase();
  for (var i = 0; i < SKIP_SENDER_PATTERNS.length; i++) {
    if (f.indexOf(SKIP_SENDER_PATTERNS[i]) > -1) return true;
  }
  return false;
}

function extractName(from) {
  var m = from.match(/^\s*"?([^"<]+?)"?\s*</);   // "Name <email>" -> Name
  if (m && m[1].trim()) return m[1].trim();
  var e = from.match(/([^<@\s]+)@/);              // else local part of email
  return e ? e[1] : '';
}

function sanitizeLabelName(name) {
  if (!name) return '';
  return name.replace(/[\/\\]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 40);
}

function getOrCreateLabel(name) {
  return GmailApp.getUserLabelByName(name) || GmailApp.createLabel(name);
}

function threadHasLabel(thread, labelName) {
  return thread.getLabels().some(function (l) { return l.getName() === labelName; });
}

/** Optional: run to remove the trigger and pause the auto-drafter. */
function stop() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'runAutoDrafter') ScriptApp.deleteTrigger(t);
  });
  Logger.log('Auto-drafter stopped (trigger removed).');
}
