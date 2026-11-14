// DAEMON Engineering Solutions — Cloudflare Worker
// Public lead intake is stored in D1. Admin access uses a signed, HttpOnly session cookie.
const SESSION_SECONDS = 12 * 60 * 60;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === "/api/health" && request.method === "GET") {
      return json({ ok: true, lead_storage_configured: Boolean(env.DB), email_notifications: "disabled" });
    }
    if (path === "/api/leads" && request.method === "POST") return handleLead(request, env);
    if (path === "/api/admin/login" && request.method === "POST") return adminLogin(request, env);
    if (path === "/api/admin/session" && request.method === "GET") {
      const valid = await hasAdminSession(request, env);
      return json({ authenticated: valid });
    }
    if (path === "/api/admin/logout" && request.method === "POST") {
      return new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
          "Set-Cookie": "daemon_admin=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0" }
      });
    }
    if (path === "/api/admin/leads" && request.method === "GET") {
      if (!await hasAdminSession(request, env)) return json({ error: "Unauthorized." }, 401);
      if (!env.DB) return json({ error: "D1 is not configured yet." }, 503);
      const result = await env.DB.prepare(
        "SELECT id, name, email, company, request_type, pain, status, created_at FROM leads ORDER BY id DESC LIMIT 250"
      ).all();
      return json({ leads: result.results || [] });
    }
    if (path === "/api/admin/leads/status" && request.method === "PATCH") {
      if (!await hasAdminSession(request, env)) return json({ error: "Unauthorized." }, 401);
      if (!env.DB) return json({ error: "D1 is not configured yet." }, 503);
      const body = await readJson(request);
      const id = Number(body?.id);
      const status = String(body?.status || "");
      if (!Number.isInteger(id) || id < 1 || !["new", "contacted", "qualified", "closed"].includes(status)) {
        return json({ error: "Invalid lead status update." }, 400);
      }
      await env.DB.prepare("UPDATE leads SET status = ? WHERE id = ?").bind(status, id).run();
      return json({ ok: true });
    }
    return env.ASSETS.fetch(request);
  }
};

async function handleLead(request, env) {
  if (!sameOrigin(request)) return json({ error: "Origin not allowed." }, 403);
  if (!env.DB) return json({ error: "Lead storage is being configured. Please try again shortly." }, 503);
  if (!(request.headers.get("Content-Type") || "").toLowerCase().includes("application/json")) {
    return json({ error: "JSON required." }, 415);
  }
  const body = await readJson(request);
  if (!body) return json({ error: "Invalid request." }, 400);
  if (String(body.website || "").trim()) return json({ ok: true }); // honeypot
  const name = clean(body.name, 120);
  const email = clean(body.email, 254).toLowerCase();
  const company = clean(body.company, 160);
  const pain = clean(body.pain, 3000);
  const requestType = clean(body.requestType || "Pilot inquiry", 80);
  if (!name || !company || !pain || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return json({ error: "Please complete all fields with a valid email address." }, 400);
  }
  await env.DB.prepare(
    "INSERT INTO leads (name, email, company, request_type, pain, status, created_at) VALUES (?, ?, ?, ?, ?, 'new', datetime('now'))"
  ).bind(name, email, company, requestType, pain).run();
  return json({ ok: true, stored: true });
}

async function adminLogin(request, env) {
  if (!sameOrigin(request)) return json({ error: "Origin not allowed." }, 403);
  if (!env.DASHBOARD_PASSWORD) return json({ error: "Dashboard password is not configured." }, 503);
  const body = await readJson(request);
  const supplied = String(body?.password || "");
  if (!supplied || !(await constantTimeEqual(supplied, env.DASHBOARD_PASSWORD))) {
    return json({ error: "Incorrect password." }, 401);
  }
  const expires = Math.floor(Date.now() / 1000) + SESSION_SECONDS;
  const signature = await sign(String(expires), env.DASHBOARD_PASSWORD);
  return new Response(JSON.stringify({ ok: true }), {
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      "Set-Cookie": "daemon_admin=" + expires + "." + signature + "; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=" + SESSION_SECONDS }
  });
}

async function hasAdminSession(request, env) {
  if (!env.DASHBOARD_PASSWORD) return false;
  const cookie = request.headers.get("Cookie") || "";
  const match = cookie.split(";").map(x => x.trim()).find(x => x.startsWith("daemon_admin="));
  if (!match) return false;
  const token = match.slice("daemon_admin=".length);
  const dot = token.indexOf(".");
  if (dot < 1) return false;
  const expires = token.slice(0, dot);
  const signature = token.slice(dot + 1);
  if (!/^\d+$/.test(expires) || Number(expires) < Math.floor(Date.now() / 1000)) return false;
  const expected = await sign(expires, env.DASHBOARD_PASSWORD);
  return constantTimeEqual(signature, expected);
}
async function sign(value, secret) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(value));
  return btoa(String.fromCharCode(...new Uint8Array(sig))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}
async function constantTimeEqual(a, b) {
  const aa = new TextEncoder().encode(String(a)), bb = new TextEncoder().encode(String(b));
  let diff = aa.length ^ bb.length;
  const n = Math.max(aa.length, bb.length);
  for (let i = 0; i < n; i++) diff |= (aa[i] || 0) ^ (bb[i] || 0);
  return diff === 0;
}
function sameOrigin(request) {
  const origin = request.headers.get("Origin");
  return !origin || origin === new URL(request.url).origin;
}
async function readJson(request) {
  try {
    const raw = await request.text();
    if (raw.length > 12000) return null;
    return JSON.parse(raw);
  } catch { return null; }
}
function clean(value, max) {
  return String(value == null ? "" : value).replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, max);
}
function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" }
  });
}
