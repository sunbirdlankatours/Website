/* Emails each new trip letter or enquiry form from the website to the team's Gmail, as well as keeping it in the
   inquiry box and ringing the phones. It uses Cloudflare Email Routing's own sending (the MAILER binding in
   wrangler.toml), which may only send to a verified destination address: the team's Gmail.
   Pressing Reply on that email answers the traveller (Reply-To is their address).
   If MAILER isn't set up, or sending fails, nothing else changes: the letter is kept and the phones still ring. */

import { EmailMessage } from "cloudflare:email";
import { enc } from "./common.js";

const FROM = "inquiries@sunbirdtours.lk";     // any address on the domain (its replies would reach Gmail too)
const TO = "sunbirdlankatours@gmail.com";     // must match destination_address in wrangler.toml
const SITE = "https://sunbirdtours.lk";

// the parts of a letter, in the order the email lists them
const LABELS = [
  ["name", "Name"], ["email", "Email"], ["phone", "Phone / WhatsApp"], ["country", "Country"],
  ["travellers", "Travellers"], ["adults", "Adults"], ["children", "Children"],
  ["arrival", "Arrival"], ["arrival_date", "Arrival date"], ["days", "Days"], ["dates", "Dates"],
  ["tour", "Tour"], ["interests", "Interests"],
];

// sends it after the answer has gone back to the website, so the traveller never waits for it
export function mailLater(c, d, id) {
  if (!c.env.MAILER) return;
  const p = mailLetter(c.env, d, id).catch(e => console.error("mail:", e));
  if (c.ctx && c.ctx.waitUntil) c.ctx.waitUntil(p);
}

export async function mailLetter(env, d, id) {
  const from = env.MAIL_FROM || FROM, to = env.MAIL_TO || TO;
  await env.MAILER.send(new EmailMessage(from, to, letterEmail(d, id, from, to, new Date())));
}

// the whole email as plain text (RFC 5322 + MIME), exported so it can be checked on its own
export function letterEmail(d, id, from, to, now) {
  const name = oneLine(d.name || "A traveller");
  const what = /form/i.test(d.form || "") ? "enquiry" : "trip letter"; // the site sends form "Letter" or "Form"
  // the website writes a subject like "Tour enquiry: Cultural Triangle – Anna" or "Trip plan request – Anna"
  const subject = "New " + what + ": " + (d.subject ? oneLine(d.subject) : name + (d.tour ? " - " + oneLine(d.tour) : ""));
  const page = d.page ? (/^https?:\/\//.test(d.page) ? oneLine(d.page) : SITE + oneLine(d.page)) : "";
  const lines = ["A new " + what + " came in on the website.", ""];
  for (const [k, label] of LABELS) if (d[k]) lines.push(label + ": " + oneLine(d[k]));
  if (d.message) lines.push("", "Message:", String(d.message).replace(/\r\n?/g, "\n"));
  lines.push("",
    "Press Reply to answer " + name + " directly (it goes to " + oneLine(d.email) + ").",
    "It is also in the SunBird app and the admin panel: " + SITE + "/admin/ (Inquiries, letter " + id + ").",
    "Sent " + sriLankaTime(now) + (page ? " from " + page : "") + ".");
  const reply = oneLine(d.email);
  const head = [
    "From: " + mailbox("Sunbird website", from),
    "To: " + to,
    // Reply goes to the traveller (only a plain address is trusted in a header)
    ...(/^[^\s@<>()\[\],;:"\\]+@[^\s@<>()\[\],;:"\\]+$/.test(reply) ? ["Reply-To: " + mailbox(name, reply)] : []),
    "Subject: " + headerText(subject),
    "Date: " + now.toUTCString(),
    "Message-ID: <letter-" + id + "-" + now.getTime() + "@" + from.split("@")[1] + ">",
    "MIME-Version: 1.0",
    "Content-Type: text/plain; charset=UTF-8",
    "Content-Transfer-Encoding: base64",
  ];
  return head.join("\r\n") + "\r\n\r\n" + base64Lines(enc.encode(lines.join("\r\n").replace(/\r?\n/g, "\r\n")));
}

// one line of text: no line breaks can sneak into a header
const oneLine = v => String(v == null ? "" : v).replace(/[\r\n\t]+/g, " ").trim();

// "Name" <address>, the name encoded when it has letters outside plain English
function mailbox(name, address) {
  const n = oneLine(name).replace(/["\\]/g, "");
  return (/^[\x20-\x7e]*$/.test(n) ? '"' + n + '"' : headerText(n)) + " <" + address + ">";
}

// a header's text as it is when plain, or as UTF-8 encoded words (RFC 2047) of a few letters each
function headerText(s) {
  if (/^[\x20-\x7e]*$/.test(s)) return s;
  const words = [];
  let part = "";
  for (const ch of s) {
    if (enc.encode(part + ch).length > 39) { words.push(part); part = ""; }
    part += ch;
  }
  if (part) words.push(part);
  return words.map(w => "=?UTF-8?B?" + base64(enc.encode(w)) + "?=").join("\r\n ");
}

function base64(bytes) {
  let s = "";
  for (let i = 0; i < bytes.length; i += 8192) s += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(s);
}
const base64Lines = bytes => base64(bytes).replace(/.{1,76}/g, "$&\r\n");

// "26 Nov 2026, 3:05 pm (Sri Lanka time)": Sri Lanka is always 5 h 30 min ahead of UTC
function sriLankaTime(now) {
  const t = new Date(now.getTime() + 330 * 60e3);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const h = t.getUTCHours(), m = String(t.getUTCMinutes()).padStart(2, "0");
  return t.getUTCDate() + " " + months[t.getUTCMonth()] + " " + t.getUTCFullYear() + ", "
    + ((h + 11) % 12 + 1) + ":" + m + (h < 12 ? " am" : " pm") + " (Sri Lanka time)";
}
