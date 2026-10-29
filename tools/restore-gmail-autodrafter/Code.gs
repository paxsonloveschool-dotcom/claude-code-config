/**
 * Restore — Gmail Auto-Drafter (Google Apps Script)
 * Same as the HP version, branded for Restore. Uses Google's FREE Gemini AI.
 * Drafts replies in Restore's voice, labels them, NEVER sends.
 * Setup: paste into script.google.com signed in as the Restore account,
 * add GEMINI_API_KEY in Script Properties, run setup() once.
 */

var TIMEZONE = 'America/Chicago';
var BUSINESS_START_HOUR = 8;
var BUSINESS_END_HOUR   = 19;
var DRAFT_LABEL = '📝 Email In Draft';
var GEMINI_MODEL = 'gemini-2.5-flash';
var MAX_THREADS_PER_RUN = 25;

var SKIP_SENDER_PATTERNS = [
  'no-reply', 'noreply', 'notification', 'notifications', 'mailer-daemon', 'donotreply',
  'quickbooks', 'intuit', 'getjobber', 'planhub', 'capitalone', 'johndeere', 'chase',
  'paypal', 'rapidfinance', 'accounts.google', 'sc-noreply', 'googleads', 'business profile',
  'procoretech', 'texasmutual', 'mailchimp', 'sendgrid', 'e-email', 'mkt.intuit'
];

function setup() {
  var props = PropertiesService.getScriptProperties();
  if (!props.getProperty('GEMINI_API_KEY')) {
    throw new Error('Add GEMINI_API_KEY in Project Settings first, then run setup() again.');
  }
  props.setProperty('CUTOFF_EPOCH', String(Math.floor(Date.now() / 1000)));
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'runAutoDrafter') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('runAutoDrafter').timeBased().everyMinutes(30).create();
  Logger.log('Setup complete — Restore auto-drafter runs every 30 min (8 AM–7 PM Central).');
}

function runAutoDrafter() {
  var hour = parseInt(Utilities.formatDate(new Date(), TIMEZONE, 'H'), 10);
  if (hour < BUSINESS_START_HOUR || hour >= BUSINESS_END_HOUR) return;
  var props = PropertiesService.getScriptProperties();
  var apiKey = props.getProperty('GEMINI_API_KEY');
  if (!apiKey) { Logger.log('No GEMINI_API_KEY set.'); return; }
  var cutoff = props.getProperty('CUTOFF_EPOCH') || '0';
  var draftLabel = getOrCreateLabel(DRAFT_LABEL);
  var threads = GmailApp.search('in:inbox after:' + cutoff, 0, MAX_THREADS_PER_RUN);
  threads.forEach(function (thread) {
    try {
      if (threadHasLabel(thread, DRAFT_LABEL)) return;
      var messages = thread.getMessages();
      var last = messages[messages.length - 1];
      var from = last.getFrom() || '';
      if (/restoremarketingco@gmail\.com/i.test(from)) return;
      if (isSkippedSender(from)) return;
      var result = draftWithAI(apiKey, from, last.getSubject(), last.getPlainBody());
      if (!result || !result.actionable || !result.body) return;
      last.createDraftReply(result.body);
      thread.addLabel(draftLabel);
      var name = sanitizeLabelName(result.clientName || extractName(from));
      if (name) thread.addLabel(getOrCreateLabel(name));
    } catch (e) {
      Logger.log('Error: ' + e);
    }
  });
}

function draftWithAI(apiKey, from, subject, body) {
  var system =
    'You draft email replies for Restore (Restore Marketing Co), a marketing company that helps ' +
    'businesses grow. Write in a warm, friendly, professional voice.\n\n' +
    'VOICE — short, warm, friendly. Greet with the person\'s first name + "!" (e.g. "Hi Caleb!"); ' +
    'if no name, "Hi there!". One or two short paragraphs. NO bullet lists. NO placeholders or brackets. ' +
    'Acknowledge their message, answer briefly, and move it forward by asking a detail or offering to ' +
    'hop on a quick call. Phrases like "we\'d love to help!", "happy to walk you through it", ' +
    '"Let me know what works best for you!".\n\n' +
    'SIGNATURE — end EXACTLY with these lines and NOTHING after (no website URL):\n' +
    'Thanks,\nThe Restore Team\nrestoremarketingco@gmail.com\n\n' +
    'CLASSIFY first. If the email is spam, marketing, an automated notification, a bill/receipt, or ' +
    'personal (NOT a real client/business inquiry), it is NOT actionable.\n\n' +
    'Reply with ONLY a JSON object, no markdown:\n' +
    '{"actionable": true|false, "clientName": "<person or company name>", "body": "<full reply incl. signature, or empty>"}';
  var user = 'From: ' + from + '\nSubject: ' + subject + '\n\nBody:\n' + (body || '').slice(0, 4000);
  var url = 'https://generativelanguage.googleapis.com/v1beta/models/' + GEMINI_MODEL +
            ':generateContent?key=' + encodeURIComponent(apiKey);
  var resp = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({
      system_instruction: { parts: [{ text: system }] },
      contents: [{ role: 'user', parts: [{ text: user }] }],
      generationConfig: { temperature: 0.7, maxOutputTokens: 800, responseMimeType: 'application/json' }
    }),
    muteHttpExceptions: true
  });
  if (resp.getResponseCode() !== 200) {
    Logger.log('Gemini error ' + resp.getResponseCode() + ': ' + resp.getContentText());
    return null;
  }
  var data = JSON.parse(resp.getContentText());
  var text = '';
  try { text = data.candidates[0].content.parts[0].text; } catch (e) { text = ''; }
  return parseJsonLoose(text);
}

function parseJsonLoose(text) {
  try {
    var s = text.indexOf('{'), e = text.lastIndexOf('}');
    if (s < 0 || e < 0) return null;
    return JSON.parse(text.substring(s, e + 1));
  } catch (err) { Logger.log('Parse error: ' + err); return null; }
}

function isSkippedSender(from) {
  var f = from.toLowerCase();
  for (var i = 0; i < SKIP_SENDER_PATTERNS.length; i++) {
    if (f.indexOf(SKIP_SENDER_PATTERNS[i]) > -1) return true;
  }
  return false;
}

function extractName(from) {
  var m = from.match(/^\s*"?([^"<]+?)"?\s*</);
  if (m && m[1].trim()) return m[1].trim();
  var e = from.match(/([^<@\s]+)@/);
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

function stop() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'runAutoDrafter') ScriptApp.deleteTrigger(t);
  });
  Logger.log('Restore auto-drafter stopped.');
}
