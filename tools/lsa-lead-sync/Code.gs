/**
 * LSA Lead Sync — Google Local Services Ads leads → Google Sheet
 *
 * Container-bound script: lives inside the "LSA" spreadsheet on the
 * higherpurposelandscaping@gmail.com account (the inbox that receives
 * Google's LSA lead notification emails).
 *
 * What it does, every 10 minutes:
 *   1. Searches Gmail for LSA lead notification emails
 *   2. Parses lead name, phone, job type, and received time from each
 *   3. Appends one row per NEW lead to the sheet (dedupes by Gmail message ID)
 *   4. Never deletes or modifies existing rows
 *
 * One-time setup: run setup() once from the Apps Script editor, approve
 * the permission prompts, done. See README.md for the 2-minute install.
 */

var SHEET_NAME = 'Leads'; // tab that receives rows; created if missing
var GMAIL_QUERY =
  '(from:local-services-ads-noreply@google.com OR from:localservices-noreply@google.com ' +
  'OR from:ads-account-noreply@google.com subject:lead) newer_than:30d';
var HEADERS = [
  'Received',
  'Lead Name',
  'Phone',
  'Job Type',
  'Lead Type',
  'Status',
  'Notes',
  'Email Subject',
  'Gmail Message ID',
];

/** Run once from the editor: authorizes scopes, builds the tab, installs the trigger, does first sync. */
function setup() {
  getOrCreateSheet_();
  // Remove any prior copies of the trigger so re-running setup never double-fires.
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'syncLeads') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('syncLeads').timeBased().everyMinutes(10).create();
  syncLeads();
}

/** Main sync: idempotent, safe to run any time. */
function syncLeads() {
  var sheet = getOrCreateSheet_();
  var seen = getSeenMessageIds_(sheet);
  var threads = GmailApp.search(GMAIL_QUERY, 0, 100);
  var newRows = [];

  threads.forEach(function (thread) {
    thread.getMessages().forEach(function (msg) {
      var id = msg.getId();
      if (seen[id]) return;
      var lead = parseLead_(msg);
      if (!lead) return; // not a lead notification (e.g. billing email)
      newRows.push([
        lead.received,
        lead.name,
        lead.phone,
        lead.jobType,
        lead.leadType,
        'New', // Status — edit by hand as you work the lead
        '',    // Notes
        lead.subject,
        id,
      ]);
      seen[id] = true;
    });
  });

  if (newRows.length) {
    // Oldest first so the sheet reads chronologically.
    newRows.sort(function (a, b) { return a[0] - b[0]; });
    sheet
      .getRange(sheet.getLastRow() + 1, 1, newRows.length, HEADERS.length)
      .setValues(newRows);
  }
  Logger.log('LSA sync: %s new lead(s) appended.', newRows.length);
}

/**
 * Pull lead fields out of one notification email.
 * Google changes these templates without notice, so every field has a
 * fallback — a lead is never dropped just because a regex missed.
 * Returns null only when the message clearly isn't a lead notification.
 */
function parseLead_(msg) {
  var subject = msg.getSubject() || '';
  if (!/lead/i.test(subject)) return null;

  var body = msg.getPlainBody() || '';

  var name =
    match_(body, /(?:Customer|Lead|Name)\s*[:\-]\s*([^\n]+)/i) ||
    match_(subject, /lead(?:\s+from)?\s*[:\-]?\s*(.+)$/i) ||
    '(see email)';

  var phone =
    match_(body, /(\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})/) || '';

  var jobType =
    match_(body, /(?:Job type|Service|Job)\s*[:\-]\s*([^\n]+)/i) || '';

  var leadType = /message/i.test(subject + body)
    ? 'Message'
    : /missed call|phone/i.test(subject + body)
      ? 'Phone'
      : 'Lead';

  return {
    received: msg.getDate(),
    name: name.trim(),
    phone: phone.trim(),
    jobType: jobType.trim(),
    leadType: leadType,
    subject: subject,
  };
}

function match_(text, re) {
  var m = text.match(re);
  return m ? m[1] : null;
}

function getOrCreateSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

/** Message IDs already logged, keyed for O(1) dedupe. */
function getSeenMessageIds_(sheet) {
  var seen = {};
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return seen;
  var idCol = HEADERS.indexOf('Gmail Message ID') + 1;
  sheet
    .getRange(2, idCol, lastRow - 1, 1)
    .getValues()
    .forEach(function (row) {
      if (row[0]) seen[row[0]] = true;
    });
  return seen;
}
