/* The live chat. A traveller writes in the chat card on the website (static/js/site.js), the team's
   phones ring (ring.js), and the team answers in the Sunbird team app. New messages and "typing" travel
   at once through the doorbell (desk.js); when a live line isn't open, the card and the app ask for
   news every few seconds instead.

   The traveller (the chat card). After the first message, with "Authorization: Chat <id>.<key>":
     POST   /api/chat               {text, page}   a message. Without a working key it starts a new chat
                                    and answers with the chat's key: {chat, key, message}
     GET    /api/chat?after=<id>    the messages after that one: {chat: {status, answering}, messages}
     PATCH  /api/chat               {contact, name?}   an email or WhatsApp number, for if they leave
   The team (Authorization: Bearer <pass>):
     GET    /api/chats              the open chats, the newest first (?status=closed for closed ones)
     GET    /api/chats?id=N         one chat and its messages (&after=<id> for only the newer ones)
     POST   /api/chats              {id, text}           a reply, signed with the member's first name
     PATCH  /api/chats              {id, read?, status?} read: the other phones stop ringing for it
     DELETE /api/chats?id=N
     POST   /api/devices            {token}   this phone rings for chats (its Firebase token)
     DELETE /api/devices            {token}   it stops
     POST   /api/devices/test       rings this person's phones once, to try them
   Both: GET /api/chat/live, a live line (index.js → liveLine).

   Ringing: a new chat (or a closed one written in again) rings every phone. More messages while nobody
   has answered give every phone a short ding; once someone has answered, only theirs. Opening or
   answering a chat hushes the other phones. A chat is forgotten a year after its last message. */

import { stop, json, iso, sha256hex, randomPass, sameText, cleanEmail, cleanName, readJson, senderOf } from "./common.js";
import { ringPhones, ringsOn } from "./ring.js";

const MAX_TEXT = 1000;          // characters in one message
const NEW_PER_HOUR = 3;         // chats one connection may start in an hour
const NEW_PER_HOUR_ALL = 60;    // chats everyone together may start in an hour (a flood stops here)
const PER_10_MIN = 40;          // messages a traveller may send in one chat in 10 minutes
const KEEP_DAYS = 365;          // a chat is forgotten this long after its last message
const STATES = ["open", "closed"];
const RING_TOKEN = /^[\w:.-]{20,4096}$/;
const SUMMARY = "id, created, updated, status, name, email, whatsapp, page, country, member, member_name, last_text, last_from, unread";

// ------------------------------------------------------------------ the tables (made by index.js → ready)
export function tables(db) {
  return [
    db.prepare(`CREATE TABLE IF NOT EXISTS chats (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created TEXT NOT NULL,
      updated TEXT NOT NULL,
      key TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'open',
      name TEXT NOT NULL DEFAULT '',
      email TEXT NOT NULL DEFAULT '',
      whatsapp TEXT NOT NULL DEFAULT '',
      page TEXT NOT NULL DEFAULT '',
      country TEXT NOT NULL DEFAULT '',
      sender TEXT NOT NULL DEFAULT '',
      member INTEGER NOT NULL DEFAULT 0,
      member_name TEXT NOT NULL DEFAULT '',
      last_text TEXT NOT NULL DEFAULT '',
      last_from TEXT NOT NULL DEFAULT '',
      unread INTEGER NOT NULL DEFAULT 0
    )`),
    db.prepare("CREATE INDEX IF NOT EXISTS chats_list ON chats (status, updated)"),
    db.prepare("CREATE INDEX IF NOT EXISTS chats_sender ON chats (sender, created)"),
    db.prepare(`CREATE TABLE IF NOT EXISTS chat_messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      chat INTEGER NOT NULL,
      at TEXT NOT NULL,
      who TEXT NOT NULL,
      member INTEGER NOT NULL DEFAULT 0,
      name TEXT NOT NULL DEFAULT '',
      text TEXT NOT NULL
    )`),
    db.prepare("CREATE INDEX IF NOT EXISTS chat_messages_chat ON chat_messages (chat, id)"),
    db.prepare(`CREATE TABLE IF NOT EXISTS devices (
      token TEXT PRIMARY KEY,
      member INTEGER NOT NULL,
      session TEXT NOT NULL,
      platform TEXT NOT NULL DEFAULT 'android',
      created TEXT NOT NULL,
      seen TEXT NOT NULL
    )`),
    db.prepare("CREATE INDEX IF NOT EXISTS devices_member ON devices (member)"),
  ];
}

// ------------------------------------------------------------------ small helpers
export const firstName = me => cleanName(me.name).split(" ")[0] || "Sunbird team";
const preview = text => text.replace(/\s+/g, " ").slice(0, 160);

function cleanText(v) {
  const s = String(v == null ? "" : v).replace(/\r\n?/g, "\n")
    .replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, "").replace(/\n{4,}/g, "\n\n\n").trim();
  if (s.length > MAX_TEXT) stop(400, "That message is too long (1,000 characters at most).");
  return s;
}

// the page they wrote from, as a path on the site ("/tours/ella/")
function cleanPage(v) {
  const s = String(v == null ? "" : v).trim().slice(0, 300);
  return /^\/[^\s]*$/.test(s) ? s : "";
}

const summaryOf = (db, id) => db.prepare("SELECT " + SUMMARY + " FROM chats WHERE id = ?").bind(id).first();

// work done after the answer has gone back (ringing, the doorbell)
function later(c, fn) {
  const p = Promise.resolve().then(fn).catch(e => console.error("chat, later:", e));
  if (c.ctx && c.ctx.waitUntil) c.ctx.waitUntil(p);
  return p;
}

// ------------------------------------------------------------------ the doorbell (desk.js)
export const deskOf = env => (env.DESK ? env.DESK.get(env.DESK.idFromName("desk")) : null);

// event: {chat, visitor?: message for the traveller's live lines, team?: for the team's,
//         close?: true closes the traveller's lines, kick?: member id whose lines close}
async function tell(env, event) {
  const desk = deskOf(env);
  if (!desk) return;
  try { await desk.ring(event); } catch (e) { console.error("doorbell:", e); }
}
export const kick = (env, member) => tell(env, { kick: member });

const ring = (env, db, what) => ringPhones(env, db, what).catch(e => console.error("ring:", e));

// ------------------------------------------------------------------ the traveller's side
export async function chatByKey(db, id, key) {
  if (!id || !key) return null;
  const row = await db.prepare("SELECT * FROM chats WHERE id = ?").bind(id).first();
  if (!row || !sameText(row.key, await sha256hex(key))) return null;
  return row;
}

function visitorChat({ request, db }) {
  const m = /^Chat\s+(\d+)\.(\S+)$/i.exec(request.headers.get("Authorization") || "");
  return m ? chatByKey(db, Number(m[1]), m[2]) : null;
}

async function forgetOld(db) {
  const cut = iso(KEEP_DAYS * 864e5);
  await db.batch([
    db.prepare("DELETE FROM chat_messages WHERE chat IN (SELECT id FROM chats WHERE updated < ?)").bind(cut),
    db.prepare("DELETE FROM chats WHERE updated < ?").bind(cut),
  ]);
}

export async function visitorSend(c) {
  const { request, env, db } = c;
  const b = await readJson(request);
  const text = cleanText(b.text);
  if (!text) stop(400, "Write a message first.");
  const page = cleanPage(b.page);
  const now = iso();
  let row = await visitorChat(c);
  let key = "", kind = "ding", to = "all";
  if (!row) { // a new chat
    const sender = await senderOf(request, env);
    const [mine, all] = await Promise.all([
      db.prepare("SELECT COUNT(*) AS n FROM chats WHERE sender = ? AND created > ?").bind(sender, iso(3600e3)).first(),
      db.prepare("SELECT COUNT(*) AS n FROM chats WHERE created > ?").bind(iso(3600e3)).first(),
    ]);
    if ((mine && mine.n >= NEW_PER_HOUR) || (all && all.n >= NEW_PER_HOUR_ALL)) {
      stop(429, "We couldn't start a chat just now. Please try again in a while, or message us on WhatsApp.");
    }
    await forgetOld(db);
    key = randomPass();
    const r = await db.prepare("INSERT INTO chats (created, updated, key, page, country, sender) VALUES (?, ?, ?, ?, ?, ?)")
      .bind(now, now, await sha256hex(key), page, (request.cf && request.cf.country) || "", sender).run();
    row = { id: r.meta.last_row_id, status: "open", member: 0 };
    kind = "ring";
  } else {
    const r = await db.prepare("SELECT COUNT(*) AS n FROM chat_messages WHERE chat = ? AND who = 'visitor' AND at > ?")
      .bind(row.id, iso(600e3)).first();
    if (r && r.n >= PER_10_MIN) stop(429, "That's a lot of messages in a short time. Please wait a few minutes.");
    if (row.status === "closed") kind = "ring"; // written in again: it's news for everyone
    else if (row.member) to = row.member;      // someone is answering: only their phone
  }
  const [ins] = await db.batch([
    db.prepare("INSERT INTO chat_messages (chat, at, who, text) VALUES (?, ?, 'visitor', ?)").bind(row.id, now, text),
    db.prepare("UPDATE chats SET updated = ?, status = 'open', page = CASE WHEN ? = '' THEN page ELSE ? END, last_text = ?, "
      + "last_from = 'visitor', unread = unread + 1 WHERE id = ?").bind(now, page, page, preview(text), row.id),
  ]);
  const message = { id: ins.meta.last_row_id, at: now, who: "visitor", member: 0, name: "", text };
  later(c, async () => {
    const summary = await summaryOf(db, row.id);
    await Promise.all([
      tell(env, { chat: row.id, visitor: { t: "message", message }, team: { t: "message", chat: row.id, message, summary } }),
      ring(env, db, { kind, chat: row.id, to: kind === "ring" ? "all" : to }),
    ]);
  });
  return json(Object.assign({ chat: row.id, message }, key ? { key } : {}));
}

export async function visitorRead(c) {
  const row = await visitorChat(c);
  if (!row) stop(404, "That chat isn't there any more.", { gone: true });
  const after = Math.max(0, Number(c.url.searchParams.get("after")) || 0);
  const messages = (await c.db.prepare(
    "SELECT id, at, who, name, text FROM chat_messages WHERE chat = ? AND id > ? ORDER BY id LIMIT 300"
  ).bind(row.id, after).all()).results || [];
  return json({ chat: { id: row.id, status: row.status, answering: row.member_name || "" }, messages });
}

export async function visitorContact(c) {
  const { request, env, db } = c;
  const row = await visitorChat(c);
  if (!row) stop(404, "That chat isn't there any more.", { gone: true });
  const b = await readJson(request);
  const raw = String(b.contact == null ? "" : b.contact).trim().slice(0, 200);
  let email = "", whatsapp = "";
  if (raw.includes("@")) {
    email = cleanEmail(raw);
    if (!email) stop(400, "That email address doesn't look right.");
  } else {
    const digits = raw.replace(/\D/g, "");
    if (digits.length < 7 || digits.length > 15) stop(400, "Type an email address, or a WhatsApp number with its country code.");
    whatsapp = (raw.startsWith("+") || raw.startsWith("00") ? "+" : "") + digits.replace(/^00/, "");
  }
  const name = b.name == null ? null : cleanName(b.name) || null;
  await db.prepare("UPDATE chats SET email = CASE WHEN ? = '' THEN email ELSE ? END, "
    + "whatsapp = CASE WHEN ? = '' THEN whatsapp ELSE ? END, name = COALESCE(?, name) WHERE id = ?")
    .bind(email, email, whatsapp, whatsapp, name, row.id).run();
  later(c, async () => tell(env, { chat: row.id, team: { t: "chat", summary: await summaryOf(db, row.id) } }));
  return json({ ok: true, email, whatsapp });
}

// ------------------------------------------------------------------ the team's side
export async function teamRead({ url, db }, me) {
  const id = Number(url.searchParams.get("id")) || 0;
  if (id) {
    const chat = await summaryOf(db, id);
    if (!chat) stop(404, "That chat isn't there any more.", { gone: true });
    const after = Math.max(0, Number(url.searchParams.get("after")) || 0);
    const messages = (await db.prepare(
      "SELECT id, at, who, member, name, text FROM chat_messages WHERE chat = ? AND id > ? ORDER BY id DESC LIMIT 500"
    ).bind(id, after).all()).results || [];
    return json({ chat, messages: messages.reverse() });
  }
  const status = url.searchParams.get("status") === "closed" ? "closed" : "open";
  const items = (await db.prepare("SELECT " + SUMMARY + " FROM chats WHERE status = ? ORDER BY updated DESC LIMIT 200")
    .bind(status).all()).results || [];
  const w = await db.prepare("SELECT COUNT(*) AS n FROM chats WHERE status = 'open' AND unread > 0").first();
  return json({ items, waiting: w ? w.n : 0, me: me.id });
}

export async function teamReply(c, me) {
  const { request, env, db } = c;
  const b = await readJson(request);
  const id = Number(b.id);
  if (!id) stop(400, "Which chat?");
  const text = cleanText(b.text);
  if (!text) stop(400, "Write a reply first.");
  const row = await db.prepare("SELECT id, unread FROM chats WHERE id = ?").bind(id).first();
  if (!row) stop(404, "That chat isn't there any more.", { gone: true });
  const name = firstName(me), now = iso();
  const [ins] = await db.batch([
    db.prepare("INSERT INTO chat_messages (chat, at, who, member, name, text) VALUES (?, ?, 'team', ?, ?, ?)").bind(id, now, me.id, name, text),
    db.prepare("UPDATE chats SET updated = ?, status = 'open', member = ?, member_name = ?, last_text = ?, last_from = 'team', "
      + "unread = 0 WHERE id = ?").bind(now, me.id, name, preview(text), id),
  ]);
  const message = { id: ins.meta.last_row_id, at: now, who: "team", member: me.id, name, text };
  later(c, async () => {
    const summary = await summaryOf(db, id);
    await Promise.all([
      tell(env, { chat: id, visitor: { t: "message", message: Object.assign({}, message, { member: 0 }) },
        team: { t: "message", chat: id, message, summary } }),
      row.unread ? ring(env, db, { kind: "hush", chat: id, except: me.id }) : null,
    ]);
  });
  return json({ ok: true, message });
}

export async function teamChange(c, me) {
  const { request, env, db } = c;
  const b = await readJson(request);
  const id = Number(b.id);
  if (!id) stop(400, "Which chat?");
  if (b.status != null && !STATES.includes(b.status)) stop(400, "Unknown status.");
  if (b.status == null && !b.read) stop(400, "Nothing to change.");
  const row = await db.prepare("SELECT id, unread FROM chats WHERE id = ?").bind(id).first();
  if (!row) stop(404, "That chat isn't there any more.", { gone: true });
  await db.prepare("UPDATE chats SET status = COALESCE(?, status), unread = CASE WHEN ? = 1 THEN 0 ELSE unread END WHERE id = ?")
    .bind(b.status == null ? null : b.status, b.read ? 1 : 0, id).run();
  later(c, async () => Promise.all([
    tell(env, { chat: id, team: { t: "chat", summary: await summaryOf(db, id) } }),
    b.read && row.unread ? ring(env, db, { kind: "hush", chat: id, except: me.id }) : null,
  ]));
  return json({ ok: true });
}

export async function teamDelete(c) {
  const { url, env, db } = c;
  const id = Number(url.searchParams.get("id"));
  if (!id) stop(400, "Which chat?");
  await db.batch([
    db.prepare("DELETE FROM chat_messages WHERE chat = ?").bind(id),
    db.prepare("DELETE FROM chats WHERE id = ?").bind(id),
  ]);
  later(c, () => Promise.all([
    tell(env, { chat: id, team: { t: "gone", chat: id }, close: true }),
    ring(env, db, { kind: "hush", chat: id }),
  ]));
  return json({ ok: true });
}

// ------------------------------------------------------------------ the phones that ring
export async function addDevice({ request, env, db }, me) {
  const b = await readJson(request);
  const token = String(b.token || "");
  if (!RING_TOKEN.test(token)) stop(400, "That isn't a phone's ring token.");
  const now = iso();
  await db.batch([
    db.prepare("INSERT INTO devices (token, member, session, created, seen) VALUES (?, ?, ?, ?, ?) "
      + "ON CONFLICT(token) DO UPDATE SET member = excluded.member, session = excluded.session, seen = excluded.seen")
      .bind(token, me.id, me.token, now, now),
    db.prepare("DELETE FROM devices WHERE session NOT IN (SELECT token FROM sessions)"), // signed out elsewhere
  ]);
  return json({ ok: true, rings: ringsOn(env) });
}

export async function removeDevice({ request, db }, me) {
  const b = await readJson(request);
  await db.prepare("DELETE FROM devices WHERE token = ? AND member = ?").bind(String(b.token || ""), me.id).run();
  return json({ ok: true });
}

export async function testRing({ env, db }, me) {
  if (!ringsOn(env)) {
    stop(503, "Phone rings aren't switched on yet. In Cloudflare, add the FCM_SERVICE_ACCOUNT secret to the inquiry box.", { setup: "fcm" });
  }
  const r = await ringPhones(env, db, { kind: "test", to: me.id });
  if (!r.sent) stop(404, "No phone of yours is set to ring yet. Open the app on your phone and allow notifications.");
  return json({ ok: true, sent: r.sent });
}
