// DAEMON ACE site Worker: static assets + secure lead-email endpoint.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/api/health" && request.method === "GET") {
      return json({ ok: true, lead_delivery_configured: Boolean(env.RESEND_API_KEY && env.LEAD_TO_EMAIL && env.LEAD_FROM_EMAIL) });
    }
    if (url.pathname === "/api/leads") {
      if (request.method !== "POST") return json({ error: "Method not allowed." }, 405, { Allow: "POST" });
      return handleLead(request, env);
    }
    return env.ASSETS.fetch(request);
  }
};

async function handleLead(request, env) {
  const origin = request.headers.get("Origin");
  const ownOrigin = new URL(request.url).origin;
  if (origin && origin !== ownOrigin) return json({ error: "Origin not allowed." }, 403);
  if (!(request.headers.get("Content-Type") || "").toLowerCase().includes("application/json")) {
    return json({ error: "JSON required." }, 415);
  }
  let raw;
  try { raw = await request.text(); } catch { return json({ error: "Invalid request." }, 400); }
  if (raw.length > 12000) return json({ error: "Request too large." }, 413);
  let data;
  try { data = JSON.parse(raw); } catch { return json({ error: "Invalid request." }, 400); }
  // Honeypot: silently accept bot submissions without sending email.
  if (String(data.website || "").trim()) return json({ ok: true });
  const name = clean(data.name, 120);
  const email = clean(data.email, 254);
  const company = clean(data.company, 160);
  const pain = clean(data.pain, 3000);
  const requestType = clean(data.requestType || "Pilot inquiry", 80);
  if (!name || !company || !pain || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return json({ error: "Please complete all fields with a valid email address." }, 400);
  }
  if (!env.RESEND_API_KEY || !env.LEAD_TO_EMAIL || !env.LEAD_FROM_EMAIL) {
    return json({ error: "Lead delivery is not configured yet. Please email barry.ellison@comcast.net." }, 503);
  }
  const message = [
    "DAEMON ACE website inquiry",
    "Request type: " + requestType,
    "Name: " + name,
    "Work email: " + email,
    "Organization: " + company,
    "",
    "Project / request details:",
    pain,
    "",
    "Submitted: " + new Date().toISOString()
  ].join("\n");
  const sent = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: "Bearer " + env.RESEND_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: env.LEAD_FROM_EMAIL,
      to: [env.LEAD_TO_EMAIL],
      reply_to: email,
      subject: "[DAEMON ACE] " + requestType + " — " + company,
      text: message
    })
  });
  if (!sent.ok) return json({ error: "The email service could not accept the request. Please try again or email barry.ellison@comcast.net." }, 502);
  return json({ ok: true });
}
function clean(value, max) {
  return String(value == null ? "" : value).replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, max);
}
function json(body, status = 200, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...extra }
  });
}
