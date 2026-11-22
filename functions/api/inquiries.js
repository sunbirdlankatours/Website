/* The inquiry box: trip letters and enquiry forms sent from the website, kept in a Cloudflare D1
   database so the admin panel can show them (Inquiries). Runs as a Cloudflare Pages Function.

     POST   /api/inquiries        the website sends a letter or a form           (anyone)
     GET    /api/inquiries        the admin panel lists them                     (admins)
     PATCH  /api/inquiries        the admin panel marks one replied, adds a note (admins)
     DELETE /api/inquiries?id=N   the admin panel deletes one                    (admins)

   Setting it up (once): in Cloudflare, Pages project → Settings → Bindings → Add → D1 database,
   variable name DB. The table makes itself the first time it is used.

   "Admins" are whoever signs in to the admin panel: the panel sends its GitHub key, and it is let
   in when GitHub says that key may change the site's repository (admin_repo in settings.txt). */

const STATUSES = ["new", "replied", "booked", "closed"];
// the parts of a letter or form that are kept, with the most characters kept of each
const FIELDS = {
  name: 120, email: 200, phone: 60, country: 80, travellers: 120, adults: 4, children: 4,
  arrival: 60, arrival_date: 20, days: 60, dates: 120, interests: 400, tour: 200,
  subject: 300, message: 6000, page: 500, form: 30,
};
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PER_HOUR = 10; // letters one connection may send in an hour

const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
});

async function fingerprint(text) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(d)].slice(0, 12).map(b => b.toString(16).padStart(2, "0")).join("");
}

let tableReady = null;
function ready(db) {
  if (!tableReady) {
    tableReady = db.batch([
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
        updated TEXT NOT NULL DEFAULT ''
      )`),
      db.prepare("CREATE INDEX IF NOT EXISTS inquiries_sender ON inquiries (sender, created)"),
    ]).catch(e => { tableReady = null; throw e; });
  }
  return tableReady;
}

// ------------------------------------------------------------------ the website sends one
export async function onRequestPost({ request, env }) {
  if (!env.DB) return json({ success: false, message: "The inquiry box is not connected yet." }, 503);
  // only the website's own pages may post here
  const origin = request.headers.get("Origin");
  if (origin && origin !== "null") {
    let host = "";
    try { host = new URL(origin).host; } catch (e) { /* not an address */ }
    if (host !== new URL(request.url).host) return json({ success: false, message: "Not allowed." }, 403);
  }
  if (Number(request.headers.get("Content-Length") || 0) > 40000) {
    return json({ success: false, message: "That letter is too long to send." }, 413);
  }
  let body;
  try {
    const type = request.headers.get("Content-Type") || "";
    body = type.includes("application/json") ? await request.json() : Object.fromEntries(await request.formData());
  } catch (e) {
    return json({ success: false, message: "The letter could not be read." }, 400);
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) return json({ success: false, message: "The letter could not be read." }, 400);
  if (body.botcheck) return json({ success: true }); // the hidden box that only robots tick

  const d = {};
  for (const [k, max] of Object.entries(FIELDS)) {
    const v = body[k];
    if (v == null || typeof v === "object") continue;
    const s = String(v).trim().slice(0, max);
    if (s) d[k] = s;
  }
  if (!d.name || !d.email || !EMAIL.test(d.email)) {
    return json({ success: false, message: "A name and an email address are needed." }, 400);
  }

  await ready(env.DB);
  const ip = request.headers.get("CF-Connecting-IP") || "";
  const sender = ip ? await fingerprint(ip + "|" + (env.SALT || "sunbird inquiry box")) : "";
  const now = new Date();
  if (sender) {
    const since = new Date(now.getTime() - 3600e3).toISOString();
    const r = await env.DB.prepare("SELECT COUNT(*) AS n FROM inquiries WHERE sender = ? AND created > ?").bind(sender, since).first();
    if (r && r.n >= PER_HOUR) {
      return json({ success: false, message: "Many letters came from here in the last hour. Please try again later." }, 429);
    }
  }
  await env.DB.prepare(
    "INSERT INTO inquiries (created, name, email, phone, country, tour, subject, data, sent_from, sender) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
  ).bind(now.toISOString(), d.name, d.email, d.phone || "", d.country || "", d.tour || "", d.subject || "",
    JSON.stringify(d), (request.cf && request.cf.country) || "", sender).run();
  return json({ success: true });
}

// ------------------------------------------------------------------ the admin panel
const checked = new Map(); // fingerprint of a GitHub key -> when GitHub last said yes

async function isAdmin(request, env) {
  const m = /^Bearer\s+(\S+)$/i.exec(request.headers.get("Authorization") || "");
  if (!m) return false;
  const fp = await fingerprint(m[1]);
  const t = checked.get(fp);
  if (t && Date.now() - t < 5 * 60e3) return true;
  let repo = env.ADMIN_REPO || "";
  if (!repo && env.ASSETS) {
    try {
      repo = (await (await env.ASSETS.fetch(new URL("/admin/config.json", request.url))).json()).repo || "";
    } catch (e) { /* no config */ }
  }
  if (!/^[\w.-]+\/[\w.-]+$/.test(repo)) return false;
  const r = await fetch((env.GITHUB_API || "https://api.github.com") + "/repos/" + repo, {
    headers: {
      Authorization: "Bearer " + m[1], Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "sunbird-inquiry-box",
    },
  });
  if (!r.ok) return false;
  const info = await r.json().catch(() => ({}));
  if (!info.permissions || !(info.permissions.push || info.permissions.admin)) return false;
  if (checked.size > 200) checked.clear();
  checked.set(fp, Date.now());
  return true;
}

async function guard(request, env) {
  if (!env.DB) return json({ error: "The inquiry box is not connected yet.", connected: false }, 503);
  if (!await isAdmin(request, env)) return json({ error: "This GitHub key may not read the inquiries." }, 401);
  await ready(env.DB);
  return null;
}

export async function onRequestGet({ request, env }) {
  const stop = await guard(request, env);
  if (stop) return stop;
  const before = Number(new URL(request.url).searchParams.get("before")) || 0;
  const rows = (await env.DB.prepare(
    "SELECT id, created, status, name, email, phone, country, tour, subject, data, note, sent_from, updated FROM inquiries"
    + (before ? " WHERE id < ?" : "") + " ORDER BY id DESC LIMIT 300"
  ).bind(...(before ? [before] : [])).all()).results || [];
  const counts = {};
  for (const r of (await env.DB.prepare("SELECT status, COUNT(*) AS n FROM inquiries GROUP BY status").all()).results || []) {
    counts[r.status] = r.n;
  }
  const items = rows.map(r => {
    let data = {};
    try { data = JSON.parse(r.data); } catch (e) { /* keep empty */ }
    return Object.assign({}, r, { data });
  });
  return json({ items, counts, more: rows.length === 300 });
}

export async function onRequestPatch({ request, env }) {
  const stop = await guard(request, env);
  if (stop) return stop;
  let b;
  try { b = await request.json(); } catch (e) { return json({ error: "Could not read the change." }, 400); }
  const id = Number(b && b.id);
  if (!id) return json({ error: "Which inquiry?" }, 400);
  if (b.status != null && !STATUSES.includes(b.status)) return json({ error: "Unknown status." }, 400);
  if (b.status == null && b.note == null) return json({ error: "Nothing to change." }, 400);
  const r = await env.DB.prepare(
    "UPDATE inquiries SET status = COALESCE(?, status), note = COALESCE(?, note), updated = ? WHERE id = ?"
  ).bind(b.status == null ? null : b.status, b.note == null ? null : String(b.note).slice(0, 4000), new Date().toISOString(), id).run();
  if (!r.meta || !r.meta.changes) return json({ error: "That inquiry is not there any more." }, 404);
  return json({ ok: true });
}

export async function onRequestDelete({ request, env }) {
  const stop = await guard(request, env);
  if (stop) return stop;
  const id = Number(new URL(request.url).searchParams.get("id"));
  if (!id) return json({ error: "Which inquiry?" }, 400);
  await env.DB.prepare("DELETE FROM inquiries WHERE id = ?").bind(id).run();
  return json({ ok: true });
}
