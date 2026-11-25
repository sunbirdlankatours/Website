/* Rings the team's phones through Firebase Cloud Messaging (FCM), Google's way of waking an Android
   phone that is asleep. Only a small signal goes through Google: what kind of ring and which chat.
   The app then fetches the words from the inquiry box with its own sign-in, so travellers' messages
   never pass through Firebase.

   Kinds of ring (the app decides how each one sounds):
     ring   a new chat: rings until someone picks it up
     ding   another message in a chat
     hush   someone has opened or answered that chat: stop ringing for it
     test   "Send a test ring" in the app

   Needs the FCM_SERVICE_ACCOUNT secret: the JSON key of the Firebase project's service account
   (Firebase console → Project settings → Service accounts → Generate new private key; paste the whole
   file's contents as the secret). Without it nothing rings, and the chat itself still works.
   FCM_API and FCM_TOKEN_URL can point somewhere else, for testing. */

import { enc, iso, unb64, b64url } from "./common.js";

const SCOPE = "https://www.googleapis.com/auth/firebase.messaging";
const TOKEN_URL = "https://oauth2.googleapis.com/token";
let cached = null; // Google's pass for sending, which lasts an hour: {token, until, email}

function account(env) {
  if (!env.FCM_SERVICE_ACCOUNT) return null;
  try {
    const a = JSON.parse(env.FCM_SERVICE_ACCOUNT);
    if (a && a.client_email && a.private_key && a.project_id) return a;
  } catch (e) { /* falls through */ }
  console.error("ring: FCM_SERVICE_ACCOUNT is not a Firebase service account key");
  return null;
}

export const ringsOn = env => !!account(env);

// signs in to Google as the service account (a JWT signed with its key) for an hour's sending pass
async function accessToken(env, a) {
  if (cached && cached.email === a.client_email && cached.until > Date.now() + 60e3) return cached.token;
  const now = Math.floor(Date.now() / 1000);
  const part = o => b64url(enc.encode(JSON.stringify(o)));
  const unsigned = part({ alg: "RS256", typ: "JWT" }) + "."
    + part({ iss: a.client_email, scope: SCOPE, aud: TOKEN_URL, iat: now, exp: now + 3600 });
  const pem = String(a.private_key).replace(/-----[^-]+-----/g, "").replace(/\s+/g, "");
  const key = await crypto.subtle.importKey("pkcs8", unb64(pem), { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, enc.encode(unsigned)));
  const r = await fetch(env.FCM_TOKEN_URL || TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: "grant_type=" + encodeURIComponent("urn:ietf:params:oauth:grant-type:jwt-bearer") + "&assertion=" + unsigned + "." + b64url(sig),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok || !d.access_token) throw new Error("Firebase sign-in failed: " + (d.error_description || d.error || r.status));
  cached = { token: d.access_token, until: Date.now() + (Number(d.expires_in) || 3600) * 1000, email: a.client_email };
  return cached.token;
}

// what: {kind, chat?, to?: "all" | member id, except?: member id} → {sent}
export async function ringPhones(env, db, what) {
  const a = account(env);
  if (!a) return { sent: 0, off: true };
  const to = what.to == null ? "all" : what.to;
  // only phones whose sign-in is still good
  let q = "SELECT d.token FROM devices d JOIN sessions s ON s.token = d.session WHERE s.expires > ?";
  const args = [iso()];
  if (to !== "all") { q += " AND d.member = ?"; args.push(Number(to)); }
  if (what.except) { q += " AND d.member != ?"; args.push(Number(what.except)); }
  const phones = (await db.prepare(q).bind(...args).all()).results || [];
  if (!phones.length) return { sent: 0 };

  const pass = await accessToken(env, a);
  const url = (env.FCM_API || "https://fcm.googleapis.com") + "/v1/projects/" + encodeURIComponent(a.project_id) + "/messages:send";
  const data = { kind: String(what.kind), chat: String(what.chat || ""), at: iso() };
  const gone = [];
  let sent = 0;
  await Promise.all(phones.map(async p => {
    const r = await fetch(url, {
      method: "POST",
      headers: { Authorization: "Bearer " + pass, "Content-Type": "application/json" },
      // "high" wakes a sleeping phone at once; a ring that is minutes old isn't worth ringing
      body: JSON.stringify({ message: { token: p.token, data, android: { priority: "high", ttl: what.kind === "ring" ? "600s" : "120s" } } }),
    });
    if (r.ok) { sent++; return; }
    const e = await r.json().catch(() => ({}));
    const why = JSON.stringify(e);
    if (r.status === 404 || why.includes("UNREGISTERED")) gone.push(p.token); // the app was removed, or signed out
    else console.error("ring: FCM said", r.status, why.slice(0, 300));
  }));
  if (gone.length) await db.batch(gone.map(t => db.prepare("DELETE FROM devices WHERE token = ?").bind(t)));
  return { sent };
}
