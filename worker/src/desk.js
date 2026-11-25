/* The doorbell: one Cloudflare Durable Object that holds every open live line (WebSocket), so a new
   message or "typing" reaches the other side the moment it happens.

   - The traveller's chat card has a line for its own chat (tag "chat:<id>").
   - The team's app has a line for every chat (tags "team" and "member:<id>") while it is open on screen.
   - The Worker rings here (ring(), below) whenever a message is saved or a chat changes. The messages
     themselves are kept in D1 (chat.js); nothing is stored here.
   - Lines sleep between messages ("hibernation"), so an idle line costs nothing. A line sends "ping"
     every half a minute or so to stay open, and gets "pong" without waking the doorbell.

   What travels on a line, as JSON:
     to the traveller   {t: "message", message}   {t: "typing", who: "team", name, on}
     to the team        {t: "message", chat, message, summary}   {t: "chat", summary}   {t: "gone", chat}
                        {t: "typing", chat, who: "visitor" | "team", name?, member?, on}
     to either          {t: "bye", why: "gone" | "signed out"}   just before the doorbell closes the line
     from either        {t: "typing", on, chat?}   (the team says which chat) */

import { DurableObject } from "cloudflare:workers";

export class Desk extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    ctx.setWebSocketAutoResponse(new WebSocketRequestResponsePair("ping", "pong"));
  }

  // a new line, already checked by the Worker (index.js → liveLine), which says who it is in X-Desk
  async fetch(request) {
    let info = {};
    try { info = JSON.parse(request.headers.get("X-Desk") || "{}"); } catch (e) { /* refused below */ }
    const tags = info.kind === "team" ? ["team", "member:" + info.member]
      : info.kind === "chat" ? ["chat:" + info.chat] : null;
    if (!tags || request.headers.get("Upgrade") !== "websocket") return new Response("Not allowed.", { status: 400 });
    const [client, server] = Object.values(new WebSocketPair());
    this.ctx.acceptWebSocket(server, tags);
    server.serializeAttachment(info);
    return new Response(null, { status: 101, webSocket: client, headers: info.proto ? { "Sec-WebSocket-Protocol": info.proto } : {} });
  }

  async webSocketMessage(ws, data) {
    if (typeof data !== "string" || data.length > 300) return;
    let m;
    try { m = JSON.parse(data); } catch (e) { return; }
    if (!m || m.t !== "typing") return;
    const me = ws.deserializeAttachment() || {};
    const on = !!m.on;
    if (me.kind === "chat") {
      this.send("team", { t: "typing", chat: me.chat, who: "visitor", on });
    } else if (me.kind === "team") {
      const chat = Number(m.chat);
      if (!(chat > 0)) return;
      this.send("chat:" + chat, { t: "typing", who: "team", name: me.name, on });
      this.send("team", { t: "typing", chat, who: "team", member: me.member, name: me.name, on }, ws); // colleagues see it too
    }
  }

  async webSocketClose(ws, code, reason) {
    try { ws.close(code, reason); } catch (e) { /* already closed */ }
  }

  async webSocketError(ws) {
    try { ws.close(1011, "error"); } catch (e) { /* already closed */ }
  }

  // called by the Worker (chat.js → tell)
  async ring(event) {
    if (event.kick) this.shut("member:" + event.kick, 4001, "signed out");
    if (!event.chat) return;
    if (event.visitor) this.send("chat:" + event.chat, event.visitor);
    if (event.team) this.send("team", event.team);
    if (event.close) this.shut("chat:" + event.chat, 4000, "gone");
  }

  send(tag, msg, except) {
    const s = JSON.stringify(msg);
    for (const ws of this.ctx.getWebSockets(tag)) {
      if (ws === except) continue;
      try { ws.send(s); } catch (e) { /* closing */ }
    }
  }

  // Says why first ({t: "bye", why}), then closes. A line that has never sent anything may not finish
  // closing on its side, so the card and the app hang up themselves when they hear "bye".
  shut(tag, code, reason) {
    for (const ws of this.ctx.getWebSockets(tag)) {
      try { ws.send(JSON.stringify({ t: "bye", why: reason })); } catch (e) { /* closing */ }
      try { ws.close(code, reason); } catch (e) { /* closing */ }
    }
  }
}
