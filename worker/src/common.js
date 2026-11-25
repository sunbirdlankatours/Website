/* Small helpers shared by the inquiry box (index.js), the live chat (chat.js), the doorbell (desk.js)
   and the phone rings (ring.js). */

export const enc = new TextEncoder();
export const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export class Stop extends Error {
  constructor(status, body) { super(body.error || body.message || "stop"); this.status = status; this.body = body; }
}
export const stop = (status, error, extra) => { throw new Stop(status, Object.assign({ error }, extra)); };
export const refuse = (status, message) => { throw new Stop(status, { success: false, message }); }; // for the website's letters

export const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
});
export const iso = (agoMs = 0) => new Date(Date.now() - agoMs).toISOString();

export const b64 = bytes => btoa(String.fromCharCode(...bytes));
export const unb64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
export const b64url = bytes => b64(bytes).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

export async function sha256hex(text) {
  const d = await crypto.subtle.digest("SHA-256", enc.encode(text));
  return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2, "0")).join("");
}

// a long random pass (sign-ins, chat keys), safe to put in a header
export function randomPass() {
  const b = new Uint8Array(32);
  crypto.getRandomValues(b);
  return b64url(b);
}

// compares two texts in the same time whatever they hold, so timing gives nothing away
export function sameText(a, b) {
  a = String(a); b = String(b);
  let diff = a.length ^ b.length;
  for (let i = 0; i < Math.max(a.length, b.length); i++) diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  return diff === 0;
}

export const cleanEmail = v => {
  const s = String(v == null ? "" : v).trim().toLowerCase().slice(0, 200);
  return EMAIL.test(s) ? s : "";
};
export const cleanName = v => String(v == null ? "" : v).trim().replace(/\s+/g, " ").slice(0, 80);

export async function readJson(request) {
  if (Number(request.headers.get("Content-Length") || 0) > 40000) stop(413, "That is too long to send.");
  try {
    const b = await request.json();
    if (b && typeof b === "object" && !Array.isArray(b)) return b;
  } catch (e) { /* falls through */ }
  stop(400, "Could not read what was sent.");
}

// who is asking, as a fingerprint (the address itself is never kept)
export async function senderOf(request, env) {
  const ip = request.headers.get("CF-Connecting-IP") || "local";
  return (await sha256hex(ip + "|" + (env.SALT || "sunbird inquiry box"))).slice(0, 24);
}
