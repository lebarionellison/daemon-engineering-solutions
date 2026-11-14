// Cloudflare Pages Function: POST /api/leads
// Required environment variables (set as encrypted secrets/vars in Cloudflare Pages):
// RESEND_API_KEY, LEAD_TO_EMAIL, LEAD_FROM_EMAIL
export async function onRequestPost({ request, env }) {
  const origin = request.headers.get("Origin");
  const ownOrigin = new URL(request.url).origin;
  if (origin && origin !== ownOrigin) return json({ error: "Origin not allowed." }, 403);
  const type = request.headers.get("content-type") || "";
  if (!type.includes("application/json")) return json({ error: "JSON required." }, 415);
  let data;
  try { data = await request.json(); } catch { return json({ error: "Invalid request." }, 400); }
  // Honeypot: silently accept bots without sending email.
  if (String(data.website || "").trim()) return json({ ok: true });
  const name = clean(data.name, 120);
  const email = clean(data.email, 254);
  const company = clean(data.company, 160);
  const pain = clean(data.pain, 3000);
  const requestType = clean(data.requestType || "Pilot inquiry", 80);
  if (!name || !email || !company || !pain || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return json({ error: "Please complete all fields with a valid email address." }, 400);
  }
  if (!env.RESEND_API_KEY || !env.LEAD_TO_EMAIL || !env.LEAD_FROM_EMAIL) {
    return json({ error: "Lead delivery is not configured yet. Please email barry.ellison@comcast.net." }, 503);
  }
  const textBody = [
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
    headers: { "Authorization": "Bearer " + env.RESEND_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: env.LEAD_FROM_EMAIL,
      to: [env.LEAD_TO_EMAIL],
      reply_to: email,
      subject: "[DAEMON ACE] " + requestType + " — " + company,
      text: textBody
    })
  });
  if (!sent.ok) {
    // Do not expose provider response or credentials to the browser.
    return json({ error: "The email service could not accept the request. Please try again or email barry.ellison@comcast.net." }, 502);
  }
  return json({ ok: true });
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
