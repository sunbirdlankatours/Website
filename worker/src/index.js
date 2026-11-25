/* The Sunbird inquiry box: a Cloudflare Worker that keeps trip letters and enquiry forms from the
   website in a D1 database, together with the team's sign-ins. The admin panel (/admin/ → Inquiries
   and Team) reads them from here. The website itself can live anywhere (GitHub now, Hostinger later):
   its address is inquiry_api in content/settings.txt.

   Anyone:
     POST   /api/inquiries          a trip letter or enquiry form from the website
     POST   /api/login              {email, password}               → a sign-in pass for the admin panel
     POST   /api/setup              {code, name, email, password}   → makes an account, or sets a new
                                    password for one, with the setup code (the SETUP_CODE secret)
   Team members who are signed in (Authorization: Bearer <pass>):
     GET    /api/me                 who is signed in
     POST   /api/logout             ends this sign-in
     GET    /api/inquiries          the newest 300 letters (?before=<id> for older ones)
     PATCH  /api/inquiries          {id, status?, note?}
     DELETE /api/inquiries?id=N
     GET    /api/team               everyone on the team
     POST   /api/team               {name, email, password}         adds someone
     PATCH  /api/team               {id, password, current?, name?} a new password (your own needs the current one)
     DELETE /api/team?id=N          removes someone (not yourself)
   The website's own files, for the admin panel's editors (only content/ and static/img/):
     GET    /api/site/files         every editable file: [{path, size, sha}]
     GET    /api/site/file?sha=S    one file's contents (base64)
     POST   /api/site/upload        {content, encoding: "base64"} → {sha}   a new file's contents
     POST   /api/site/save          {changes: [{path, sha} | {path, delete}], message, expected}
                                    → {commit}   saves them together as one change to the website
     GET    /api/site/status?sha=C  whether the website has been rebuilt with that change yet
   The live chat with travellers, and the phones that ring for it: see chat.js.

   Setting it up (once): in Cloudflare, give the Worker a D1 database binding called DB, and the
   secrets SETUP_CODE and GITHUB_TOKEN (a GitHub key that may change GITHUB_REPO, see wrangler.toml).
   FCM_SERVICE_ACCOUNT (a Firebase key, see ring.js) makes the team's phones ring for chats.
   The tables make themselves the first time they are used. README.md has the clicks. */

import {
  Stop, stop, refuse, json, iso, b64, unb64, sha256hex, randomPass, sameText, cleanEmail, cleanName, readJson, senderOf, enc, EMAIL,
} from "./common.js";
import * as chat from "./chat.js";
export { Desk } from "./desk.js";

const FIELDS = { // the parts of a letter or form that are kept, with the most characters kept of each
  name: 120, email: 200, phone: 60, country: 80, travellers: 120, adults: 4, children: 4,
  arrival: 60, arrival_date: 20, days: 60, dates: 120, interests: 400, tour: 200,
  subject: 300, message: 6000, page: 500, form: 30,
};
const STATUSES = ["new", "replied", "booked", "closed"];
const PER_HOUR = 10;        // letters one connection may send in an hour
const WRONG_ALLOWED = 8;    // wrong passwords or setup codes one connection may try in 15 minutes
const SESSION_DAYS = 30;    // how long a sign-in lasts
const ITERATIONS = 100000;  // rounds used to scramble passwords (the most Cloudflare allows)
// the website's own addresses; ALLOWED_ORIGINS (comma separated) in the Worker's settings adds more.
// Pages on this computer (localhost) are let in too, for trying things out.
const ORIGINS = ["https://sunbirdtours.lk", "https://www.sunbirdtours.lk", "https://sunbirdlankatours.github.io",
  "https://vockshel-gif.github.io"]; // the old test site, until it is retired

const NOT_CONNECTED = "The inquiry box is not connected to its database yet.";

// ------------------------------------------------------------------ small helpers (the rest are in common.js)
// passwords are only ever kept scrambled (PBKDF2 with a random salt), never as typed
async function scramble(password, salt = crypto.getRandomValues(new Uint8Array(16)), rounds = ITERATIONS) {
  const key = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt, iterations: rounds }, key, 256);
  return "pbkdf2-sha256$" + rounds + "$" + b64(salt) + "$" + b64(new Uint8Array(bits));
}

async function passwordMatches(password, stored) {
  const [kind, rounds, salt] = String(stored || "").split("$");
  if (kind !== "pbkdf2-sha256" || !salt) return false;
  return sameText(await scramble(String(password), unb64(salt), Number(rounds)), stored);
}

let dummy = null; // checked against when an email isn't on the team, so both take the same time
const dummyScramble = () => (dummy = dummy || scramble("not a real password"));

function checkPassword(p) {
  if (p.length < 8) stop(400, "The password needs 8 characters or more.");
  if (p.length > 200) stop(400, "That password is too long.");
}

function allowedOrigin(origin, env) {
  const extra = String(env.ALLOWED_ORIGINS || "").split(",").map(s => s.trim().replace(/\/+$/, "")).filter(Boolean);
  if (ORIGINS.includes(origin) || extra.includes(origin)) return true;
  return /^http:\/\/(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$/.test(origin);
}

// ------------------------------------------------------------------ the tables
let tablesReady = null;
function ready(db) {
  if (!tablesReady) {
    tablesReady = db.batch([
      db.prepare(`CREATE TABLE IF NOT EXISTS inquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'new',
        name TEXT NOT NULL DEFAULT '',
        email TEXT NOT NULL DEFAULT '',
        phone TEXT NOT NULL DEFAULT '',
        country TEXT NOT NULL DEFAULT '',
        tour TEXT NOT NULL DEFAULT '',
        subject TEXT NOT NULL DEFAULT '',
        data TEXT NOT NULL DEFAULT '{}',
        note TEXT NOT NULL DEFAULT '',
        sent_from TEXT NOT NULL DEFAULT '',
        sender TEXT NOT NULL DEFAULT '',
        updated TEXT NOT NULL DEFAULT '',
        updated_by TEXT NOT NULL DEFAULT ''
      )`),
      db.prepare("CREATE INDEX IF NOT EXISTS inquiries_sender ON inquiries (sender, created)"),
      db.prepare(`CREATE TABLE IF NOT EXISTS team (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL DEFAULT '',
        password TEXT NOT NULL,
        created TEXT NOT NULL,
        last_login TEXT NOT NULL DEFAULT ''
      )`),
      db.prepare(`CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        member INTEGER NOT NULL,
        created TEXT NOT NULL,
        expires TEXT NOT NULL
      )`),
      db.prepare("CREATE INDEX IF NOT EXISTS sessions_member ON sessions (member)"),
      db.prepare("CREATE TABLE IF NOT EXISTS wrong_tries (sender TEXT NOT NULL, at TEXT NOT NULL)"),
      db.prepare("CREATE INDEX IF NOT EXISTS wrong_tries_sender ON wrong_tries (sender, at)"),
      ...chat.tables(db),
    ]).catch(e => { tablesReady = null; throw e; });
  }
  return tablesReady;
}

// ------------------------------------------------------------------ the door
export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin") || "";
    const crossSite = origin !== "" && origin !== "null";
    const known = crossSite && allowedOrigin(origin, env);
    let res;
    if (crossSite && !known) {
      res = json({ success: false, message: "Not allowed.", error: "Not allowed." }, 403);
    } else if (request.method === "OPTIONS") {
      res = new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization",
          "Access-Control-Max-Age": "86400",
        },
      });
    } else {
      res = await handle(request, env, ctx);
      if (res.status === 101) return res; // a live line (WebSocket) was opened: it goes back as it is
    }
    if (known) {
      res = new Response(res.body, res);
      res.headers.set("Access-Control-Allow-Origin", origin);
      res.headers.append("Vary", "Origin");
    }
    return res;
  },
};

async function handle(request, env, ctx) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";
  const m = request.method;
  const letter = path === "/api/inquiries" && m === "POST";
  try {
    if (path === "/" || path === "/api") return json({ ok: true, name: "Sunbird inquiry box" });
    if (!env.DB) return json(letter ? { success: false, message: NOT_CONNECTED } : { error: NOT_CONNECTED, connected: false }, 503);
    await ready(env.DB);
    const c = { request, env, ctx, url, db: env.DB };

    if (path === "/api/chat") { // the traveller's side of the live chat
      if (m === "POST") return await chat.visitorSend(c);
      if (m === "GET") return await chat.visitorRead(c);
      if (m === "PATCH") return await chat.visitorContact(c);
    } else if (path === "/api/chat/live") { // a live line, for the traveller or the team
      return await liveLine(c);
    } else if (path === "/api/chats") { // the team's side
      const me = await signedIn(c);
      if (m === "GET") return await chat.teamRead(c, me);
      if (m === "POST") return await chat.teamReply(c, me);
      if (m === "PATCH") return await chat.teamChange(c, me);
      if (m === "DELETE") return await chat.teamDelete(c, me);
    } else if (path === "/api/devices") {
      const me = await signedIn(c);
      if (m === "POST") return await chat.addDevice(c, me);
      if (m === "DELETE") return await chat.removeDevice(c, me);
    } else if (path === "/api/devices/test") {
      const me = await signedIn(c);
      if (m === "POST") return await chat.testRing(c, me);
    } else if (path === "/api/inquiries") {
      if (m === "POST") return await sendLetter(c);
      const me = await signedIn(c);
      if (m === "GET") return await listLetters(c);
      if (m === "PATCH") return await changeLetter(c, me);
      if (m === "DELETE") return await deleteLetter(c);
    } else if (path === "/api/login") {
      if (m === "POST") return await login(c);
    } else if (path === "/api/setup") {
      if (m === "POST") return await setup(c);
    } else if (path === "/api/me") {
      if (m === "GET") { const me = await signedIn(c); return json({ user: { id: me.id, email: me.email, name: me.name } }); }
    } else if (path === "/api/logout") {
      if (m === "POST") return await logout(c);
    } else if (path === "/api/team") {
      const me = await signedIn(c);
      if (m === "GET") return await listTeam(c, me);
      if (m === "POST") return await addMember(c);
      if (m === "PATCH") return await changeMember(c, me);
      if (m === "DELETE") return await removeMember(c, me);
    } else if (path.startsWith("/api/site/")) {
      const me = await signedIn(c);
      const what = path.slice("/api/site/".length);
      if (what === "files" && m === "GET") return await siteFiles(c);
      if (what === "file" && m === "GET") return await siteFile(c);
      if (what === "upload" && m === "POST") return await siteUpload(c);
      if (what === "save" && m === "POST") return await siteSave(c, me);
      if (what === "status" && m === "GET") return await siteStatus(c);
      if (!["files", "file", "upload", "save", "status"].includes(what)) return json({ error: "Not found." }, 404);
    } else {
      return json({ error: "Not found." }, 404);
    }
    return json({ error: "Not allowed." }, 405);
  } catch (e) {
    if (e instanceof Stop) return json(e.body, e.status);
    console.error(e);
    const msg = "Something went wrong in the inquiry box. Please try again in a minute.";
    return json(letter ? { success: false, message: msg } : { error: msg }, 500);
  }
}

// ------------------------------------------------------------------ the website sends a letter
async function sendLetter(c) {
  const { request, env, db } = c;
  if (Number(request.headers.get("Content-Length") || 0) > 40000) refuse(413, "That letter is too long to send.");
  let body;
  try {
    const type = request.headers.get("Content-Type") || "";
    body = type.includes("application/json") ? await request.json() : Object.fromEntries(await request.formData());
  } catch (e) { refuse(400, "The letter could not be read."); }
  if (!body || typeof body !== "object" || Array.isArray(body)) refuse(400, "The letter could not be read.");
  if (body.botcheck) return json({ success: true }); // the hidden box that only robots tick

  const d = {};
  for (const [k, max] of Object.entries(FIELDS)) {
    const v = body[k];
    if (v == null || typeof v === "object") continue;
    const s = String(v).trim().slice(0, max);
    if (s) d[k] = s;
  }
  if (!d.name || !d.email || !EMAIL.test(d.email)) refuse(400, "A name and an email address are needed.");

  const sender = await senderOf(request, env);
  const r = await db.prepare("SELECT COUNT(*) AS n FROM inquiries WHERE sender = ? AND created > ?").bind(sender, iso(3600e3)).first();
  if (r && r.n >= PER_HOUR) refuse(429, "Many letters came from here in the last hour. Please try again later.");
  const saved = await db.prepare(
    "INSERT INTO inquiries (created, name, email, phone, country, tour, subject, data, sent_from, sender) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
  ).bind(iso(), d.name, d.email, d.phone || "", d.country || "", d.tour || "", d.subject || "",
    JSON.stringify(d), (request.cf && request.cf.country) || "", sender).run();
  // the team's phones get a notification and their badge goes up (the app fetches the letter itself)
  chat.ringLater(c, { kind: "inquiry", chat: saved.meta.last_row_id });
  return json({ success: true });
}

// ------------------------------------------------------------------ signing in
async function signedIn({ request, db }) {
  const m = /^Bearer\s+(\S+)$/i.exec(request.headers.get("Authorization") || "");
  if (!m) stop(401, "Please sign in.", { signin: true });
  return sessionOf(db, m[1]);
}

// the team member a sign-in pass belongs to (or a stop, if it has ended)
async function sessionOf(db, pass) {
  const token = await sha256hex(pass);
  const row = await db.prepare(
    "SELECT s.member, s.expires, t.email, t.name FROM sessions s JOIN team t ON t.id = s.member WHERE s.token = ?"
  ).bind(token).first();
  if (!row || row.expires < iso()) {
    if (row) await db.prepare("DELETE FROM sessions WHERE token = ?").bind(token).run();
    stop(401, "Your sign-in has ended. Please sign in again.", { signin: true });
  }
  return { id: row.member, email: row.email, name: row.name, token }; // token: the pass as kept (scrambled)
}

// A live line (WebSocket) to the doorbell, for new messages and "typing" the moment they happen. The
// chat card on the website asks with its chat key, the team's app with its sign-in pass. A browser
// can't add headers to a WebSocket, so the card sends its key as the second "protocol":
// ["sunbird", "chat.<id>.<key>"]; the app may use the Authorization header instead.
async function liveLine(c) {
  const { request, env, db } = c;
  if ((request.headers.get("Upgrade") || "").toLowerCase() !== "websocket") stop(426, "This address is for a live line (a WebSocket).");
  const offered = (request.headers.get("Sec-WebSocket-Protocol") || "").split(",").map(s => s.trim()).filter(Boolean);
  const cred = offered.find(p => p !== "sunbird") || "";
  const auth = request.headers.get("Authorization") || "";
  let info, m;
  if ((m = /^chat\.(\d+)\.(\S+)$/.exec(cred)) || (m = /^Chat\s+(\d+)\.(\S+)$/i.exec(auth))) {
    const row = await chat.chatByKey(db, Number(m[1]), m[2]);
    if (!row) stop(404, "That chat isn't there any more.", { gone: true });
    info = { kind: "chat", chat: row.id };
  } else if ((m = /^team\.(\S+)$/.exec(cred)) || (m = /^Bearer\s+(\S+)$/i.exec(auth))) {
    const me = await sessionOf(db, m[1]);
    info = { kind: "team", member: me.id, name: chat.firstName(me) };
  } else {
    stop(401, "Please sign in.", { signin: true });
  }
  if (offered.length) info.proto = "sunbird";
  const desk = chat.deskOf(env);
  if (!desk) stop(503, "The live line isn't switched on.");
  return desk.fetch("https://desk/live", { headers: { Upgrade: "websocket", "X-Desk": JSON.stringify(info) } });
}

async function tooManyTries(db, sender) {
  const r = await db.prepare("SELECT COUNT(*) AS n FROM wrong_tries WHERE sender = ? AND at > ?").bind(sender, iso(15 * 60e3)).first();
  if (r && r.n >= WRONG_ALLOWED) stop(429, "Too many wrong tries. Wait 15 minutes, then try again.");
}

async function wrongTry(db, sender) {
  await db.batch([
    db.prepare("INSERT INTO wrong_tries (sender, at) VALUES (?, ?)").bind(sender, iso()),
    db.prepare("DELETE FROM wrong_tries WHERE at < ?").bind(iso(864e5)),
  ]);
}

async function startSession(db, member) {
  const pass = randomPass();
  const now = iso();
  const expires = new Date(Date.now() + SESSION_DAYS * 864e5).toISOString();
  await db.batch([
    db.prepare("INSERT INTO sessions (token, member, created, expires) VALUES (?, ?, ?, ?)").bind(await sha256hex(pass), member.id, now, expires),
    db.prepare("UPDATE team SET last_login = ? WHERE id = ?").bind(now, member.id),
    db.prepare("DELETE FROM sessions WHERE expires < ?").bind(now),
  ]);
  return { token: pass, expires, user: { id: member.id, email: member.email, name: member.name } };
}

async function login({ request, env, db }) {
  const sender = await senderOf(request, env);
  await tooManyTries(db, sender);
  const b = await readJson(request);
  const email = cleanEmail(b.email);
  const row = email ? await db.prepare("SELECT id, email, name, password FROM team WHERE email = ?").bind(email).first() : null;
  const ok = await passwordMatches(String(b.password || ""), row ? row.password : await dummyScramble());
  if (!row || !ok) {
    await wrongTry(db, sender);
    stop(401, "That email or password is not right.");
  }
  return json(await startSession(db, row));
}

async function setup({ request, env, db }) {
  const code = String(env.SETUP_CODE || "");
  if (code.length < 8) {
    stop(503, "Making accounts with a setup code is switched off. In Cloudflare, add a secret called SETUP_CODE (8 characters or more) to the Worker.", { setup: "off" });
  }
  const sender = await senderOf(request, env);
  await tooManyTries(db, sender);
  const b = await readJson(request);
  if (!sameText(await sha256hex(String(b.code || "")), await sha256hex(code))) {
    await wrongTry(db, sender);
    stop(401, "That setup code is not right.");
  }
  const email = cleanEmail(b.email);
  const name = cleanName(b.name);
  const password = String(b.password || "");
  if (!email) stop(400, "Type a real email address.");
  checkPassword(password);
  const hash = await scramble(password);
  const had = await db.prepare("SELECT id FROM team WHERE email = ?").bind(email).first();
  let id;
  if (had) { // already on the team: this sets a new password (for a forgotten one)
    id = had.id;
    await db.batch([
      db.prepare("UPDATE team SET password = ?, name = CASE WHEN ? = '' THEN name ELSE ? END WHERE id = ?").bind(hash, name, name, id),
      db.prepare("DELETE FROM sessions WHERE member = ?").bind(id),
    ]);
  } else {
    const r = await db.prepare("INSERT INTO team (email, name, password, created) VALUES (?, ?, ?, ?)").bind(email, name, hash, iso()).run();
    id = r.meta.last_row_id;
  }
  const member = await db.prepare("SELECT id, email, name FROM team WHERE id = ?").bind(id).first();
  return json(Object.assign(await startSession(db, member), { reset: !!had }));
}

async function logout(c) {
  const me = await signedIn(c);
  await c.db.batch([
    c.db.prepare("DELETE FROM sessions WHERE token = ?").bind(me.token),
    c.db.prepare("DELETE FROM devices WHERE session = ?").bind(me.token), // a signed-out phone stops ringing
  ]);
  return json({ ok: true });
}

// ------------------------------------------------------------------ letters, for the team
async function listLetters({ url, db }) {
  const before = Number(url.searchParams.get("before")) || 0;
  const rows = (await db.prepare(
    "SELECT id, created, status, name, email, phone, country, tour, subject, data, note, sent_from, updated, updated_by FROM inquiries"
    + (before ? " WHERE id < ?" : "") + " ORDER BY id DESC LIMIT 300"
  ).bind(...(before ? [before] : [])).all()).results || [];
  const counts = {};
  for (const r of (await db.prepare("SELECT status, COUNT(*) AS n FROM inquiries GROUP BY status").all()).results || []) {
    counts[r.status] = r.n;
  }
  const items = rows.map(r => {
    let data = {};
    try { data = JSON.parse(r.data); } catch (e) { /* keep empty */ }
    return Object.assign({}, r, { data });
  });
  return json({ items, counts, more: rows.length === 300 });
}

async function changeLetter(c, me) {
  const { request, db } = c;
  const b = await readJson(request);
  const id = Number(b.id);
  if (!id) stop(400, "Which inquiry?");
  if (b.status != null && !STATUSES.includes(b.status)) stop(400, "Unknown status.");
  if (b.status == null && b.note == null) stop(400, "Nothing to change.");
  const r = await db.prepare(
    "UPDATE inquiries SET status = COALESCE(?, status), note = COALESCE(?, note), updated = ?, updated_by = ? WHERE id = ?"
  ).bind(b.status == null ? null : b.status, b.note == null ? null : String(b.note).slice(0, 4000), iso(), me.name || me.email, id).run();
  if (!r.meta || !r.meta.changes) stop(404, "That inquiry is not there any more.");
  if (b.status != null) chat.ringLater(c, { kind: "inquiries" }); // the phones' "new inquiries" badge changes
  return json({ ok: true });
}

async function deleteLetter(c) {
  const { url, db } = c;
  const id = Number(url.searchParams.get("id"));
  if (!id) stop(400, "Which inquiry?");
  await db.prepare("DELETE FROM inquiries WHERE id = ?").bind(id).run();
  chat.ringLater(c, { kind: "inquiries" });
  return json({ ok: true });
}

// ------------------------------------------------------------------ the team
async function listTeam({ db }, me) {
  const items = (await db.prepare("SELECT id, email, name, created, last_login FROM team ORDER BY name COLLATE NOCASE, email").all()).results || [];
  return json({ items, me: me.id });
}

async function addMember({ request, db }) {
  const b = await readJson(request);
  const email = cleanEmail(b.email);
  const name = cleanName(b.name);
  const password = String(b.password || "");
  if (!email) stop(400, "Type a real email address.");
  checkPassword(password);
  if (await db.prepare("SELECT id FROM team WHERE email = ?").bind(email).first()) stop(409, "Someone with that email is already on the team.");
  const r = await db.prepare("INSERT INTO team (email, name, password, created) VALUES (?, ?, ?, ?)")
    .bind(email, name, await scramble(password), iso()).run();
  return json({ ok: true, item: { id: r.meta.last_row_id, email, name, created: iso(), last_login: "" } });
}

async function changeMember({ request, env, db }, me) {
  const b = await readJson(request);
  const id = Number(b.id) || me.id;
  const who = await db.prepare("SELECT id, password FROM team WHERE id = ?").bind(id).first();
  if (!who) stop(404, "That person is not on the team any more.");
  const sets = [];
  if (b.name != null) {
    const name = cleanName(b.name);
    sets.push(db.prepare("UPDATE team SET name = ? WHERE id = ?").bind(name, id));
  }
  if (b.password != null) {
    const password = String(b.password);
    checkPassword(password);
    if (id === me.id) { // your own password: the current one is needed too
      const sender = await senderOf(request, env);
      await tooManyTries(db, sender);
      if (!await passwordMatches(String(b.current || ""), who.password)) {
        await wrongTry(db, sender);
        stop(401, "Your current password is not right.");
      }
    }
    sets.push(db.prepare("UPDATE team SET password = ? WHERE id = ?").bind(await scramble(password), id));
    // everyone signed in with the old password is signed out (except you, on this device)
    sets.push(db.prepare("DELETE FROM sessions WHERE member = ? AND token != ?").bind(id, id === me.id ? me.token : ""));
  }
  if (!sets.length) stop(400, "Nothing to change.");
  await db.batch(sets);
  if (b.password != null) await chat.kick(env, id); // their open live lines sign in again (or can't)
  return json({ ok: true });
}

// ------------------------------------------------------------------ the website's files
// The admin panel's editors read and save the website's texts and photos through here, so the team
// never needs a GitHub key of their own: the Worker uses the GITHUB_TOKEN secret, and only for the
// folders the panel may change. Every save becomes one commit, with the team member as its author.
const EDITABLE = ["content/", "static/img/"];
const SHA = /^[0-9a-f]{40}$/;

function canEdit(p) {
  return typeof p === "string" && p.length < 300 && EDITABLE.some(d => p.startsWith(d))
    && !p.split("/").some(s => s === "" || s === "." || s === "..") && !/[\u0000-\u001f\\:*?"<>|]/.test(p);
}

function repoOf(env) {
  const repo = String(env.GITHUB_REPO || "sunbirdlankatours/Website");
  if (!env.GITHUB_TOKEN || !/^[\w.-]+\/[\w.-]+$/.test(repo)) {
    stop(503, "Saving the website isn’t connected yet. In Cloudflare, add the GITHUB_TOKEN secret to the inquiry box.", { setup: "github" });
  }
  return { repo, branch: String(env.GITHUB_BRANCH || "main") };
}

async function github(env, path, opts = {}) {
  const { repo } = repoOf(env);
  const r = await fetch((env.GITHUB_API || "https://api.github.com") + "/repos/" + repo + path, {
    method: opts.method || "GET",
    headers: Object.assign({
      Authorization: "Bearer " + env.GITHUB_TOKEN, Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "sunbird-inquiry-box",
    }, opts.body ? { "Content-Type": "application/json" } : {}),
    body: opts.body,
  });
  const data = r.status === 204 ? {} : await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 401) stop(503, "The GitHub key in Cloudflare doesn’t work any more (it may have run out). Make a new one and put it in GITHUB_TOKEN.", { setup: "github" });
    if (opts.allow && opts.allow.includes(r.status)) return { failed: r.status };
    if (r.status === 403 || r.status === 404) stop(503, "The GitHub key in Cloudflare may not change " + repo + ". Check its repository and permissions.", { setup: "github" });
    const e = new Error("GitHub: " + (data.message || r.status));
    e.status = r.status;
    throw e;
  }
  return data;
}

async function headOf(env) {
  const { branch } = repoOf(env);
  const ref = await github(env, "/git/ref/heads/" + branch);
  const commit = await github(env, "/git/commits/" + ref.object.sha);
  const tree = await github(env, "/git/trees/" + commit.tree.sha + "?recursive=1");
  return { commit: ref.object.sha, tree: commit.tree.sha, blobs: (tree.tree || []).filter(e => e.type === "blob") };
}

async function siteFiles({ env }) {
  const hd = await headOf(env);
  return json({ commit: hd.commit, files: hd.blobs.filter(e => canEdit(e.path)).map(e => ({ path: e.path, size: e.size, sha: e.sha })) });
}

async function siteFile({ env, url }) {
  const sha = url.searchParams.get("sha") || "";
  if (!SHA.test(sha)) stop(400, "Which file?");
  const b = await github(env, "/git/blobs/" + sha);
  return json({ content: String(b.content || "").replace(/\s+/g, "") });
}

async function siteUpload({ request, env }) {
  if (Number(request.headers.get("Content-Length") || 0) > 30 * 1048576) stop(413, "That file is too big.");
  const body = await request.arrayBuffer(); // passed on as it is: {content, encoding: "base64"}
  if (!body.byteLength) stop(400, "Nothing to upload.");
  const b = await github(env, "/git/blobs", { method: "POST", body });
  return json({ sha: b.sha });
}

async function siteSave({ request, env }, me) {
  const b = await readJson(request);
  const changes = Array.isArray(b.changes) ? b.changes : [];
  if (!changes.length || changes.length > 200) stop(400, "Nothing to save.");
  for (const ch of changes) {
    if (!ch || !canEdit(ch.path)) stop(400, "The admin panel may not change " + (ch && ch.path) + ".");
    if (!ch.delete && !SHA.test(String(ch.sha || ""))) stop(400, "Something is missing from " + ch.path + ".");
  }
  const expected = b.expected && typeof b.expected === "object" ? b.expected : {};
  const message = String(b.message || "Update the website").replace(/\s+/g, " ").trim().slice(0, 200);
  const who = me.name || me.email;
  const { branch } = repoOf(env);
  for (let attempt = 0; attempt < 2; attempt++) {
    const hd = await headOf(env);
    const now = new Map(hd.blobs.map(e => [e.path, e.sha]));
    for (const [p, sha] of Object.entries(expected)) { // someone else changed it since it was opened
      if (sha && now.get(p) !== sha) stop(409, "Someone else changed " + p + " since you opened it.", { conflict: p });
    }
    const entries = [];
    for (const ch of changes) {
      if (ch.delete) { if (now.has(ch.path)) entries.push({ path: ch.path, mode: "100644", type: "blob", sha: null }); }
      else entries.push({ path: ch.path, mode: "100644", type: "blob", sha: ch.sha });
    }
    if (!entries.length) stop(400, "Nothing to save.");
    const tree = await github(env, "/git/trees", { method: "POST", body: JSON.stringify({ base_tree: hd.tree, tree: entries }) });
    const commit = await github(env, "/git/commits", {
      method: "POST",
      body: JSON.stringify({
        message: message + "\n\nSaved in the admin panel by " + who + ".",
        tree: tree.sha, parents: [hd.commit],
        author: { name: who, email: me.email, date: new Date().toISOString() },
      }),
    });
    const moved = await github(env, "/git/refs/heads/" + branch, { method: "PATCH", body: JSON.stringify({ sha: commit.sha }), allow: [409, 422] });
    if (!moved.failed) return json({ ok: true, commit: commit.sha });
    // someone saved at the same moment: try once more on top of their change
  }
  stop(409, "Someone else saved at the same moment. Please try again.");
}

async function siteStatus({ env, url }) {
  const sha = url.searchParams.get("sha") || "";
  if (!SHA.test(sha)) stop(400, "Which change?");
  const r = await github(env, "/actions/runs?head_sha=" + sha + "&per_page=5", { allow: [403, 404] });
  if (r.failed) return json({ found: false, unknown: true }); // the key may not read Actions
  const run = (r.workflow_runs || [])[0];
  return json(run ? { found: true, status: run.status, conclusion: run.conclusion, url: run.html_url } : { found: false });
}

async function removeMember({ url, env, db }, me) {
  const id = Number(url.searchParams.get("id"));
  if (!id) stop(400, "Who?");
  if (id === me.id) stop(400, "You can’t remove yourself. Ask someone else on the team to do it.");
  const r = await db.batch([
    db.prepare("DELETE FROM sessions WHERE member = ?").bind(id),
    db.prepare("DELETE FROM team WHERE id = ?").bind(id),
    db.prepare("DELETE FROM devices WHERE member = ?").bind(id), // their phones stop ringing
  ]);
  if (!r[1].meta || !r[1].meta.changes) stop(404, "That person is not on the team any more.");
  await chat.kick(env, id);
  return json({ ok: true });
}
