# DAEMON ACE lead capture setup

The website posts form submissions to `POST /api/leads`. The endpoint is implemented in the Cloudflare Worker at `worker.js`, and `wrangler.toml` routes `/api/*` requests to the Worker before static asset handling.

## Required Cloudflare configuration

Set these values on the existing Worker named `daemon-it-consulting`:

- `RESEND_API_KEY` — encrypted Worker secret from Resend
- `LEAD_TO_EMAIL` — destination inbox (currently intended: `barry.ellison@comcast.net`)
- `LEAD_FROM_EMAIL` — sender address on a domain verified in Resend

Use Cloudflare Dashboard → Workers & Pages → daemon-it-consulting → Settings → Variables and Secrets. Add the API key as a secret and the email addresses as variables. Redeploy the Worker after the code/config changes, then verify:

- `GET /api/health` returns `lead_delivery_configured: true`
- A test form submission returns success and the email arrives
- Reply-to is set to the visitor's email address

The Worker validates fields, checks same-origin requests, uses a honeypot, and forwards inquiries through Resend. It does not store leads in a database. Never commit API keys or other secrets to GitHub.

## Calendar booking

No public Calendly or Cal.com booking URL has been supplied yet, so the site does not publish a guessed link. Add the verified 15-minute event URL once it exists.
