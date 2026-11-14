# DAEMON ACE lead capture setup

The website now posts inquiries to `POST /api/leads`. The matching Cloudflare Pages Function is in `functions/api/leads.js`.

## Required setup before form submissions can be delivered

1. Deploy this repository as a **Cloudflare Pages** project (not only as a static Worker asset bundle). Pages automatically maps `functions/api/leads.js` to `/api/leads`.
2. Create or verify a Resend account and verify the sending domain used in `LEAD_FROM_EMAIL`.
3. In Cloudflare Pages → your project → Settings → Variables and Secrets, add:
   - `RESEND_API_KEY` — encrypted secret from Resend
   - `LEAD_TO_EMAIL` — destination inbox (for example, your business inquiry inbox)
   - `LEAD_FROM_EMAIL` — verified sender address on your verified domain
4. Redeploy the Pages project and submit a test inquiry from desktop and mobile.
5. Confirm the email arrives and reply-to points to the visitor's submitted email.

The function validates fields, checks the request origin, includes a honeypot field, and sends the lead via Resend. It does not store submissions in a database. Do not commit API keys or other secrets to GitHub.

## Important deployment note

The repository's static HTML can be updated on GitHub without making the Pages Function live. If the current production site is deployed as a Cloudflare Worker with static assets (rather than Cloudflare Pages), this function will not run until the backend is adapted and deployed to that Worker or the site is moved to Pages. Verify the production deployment target before announcing that lead capture is active.

## Calendar booking

The site does not yet include a public booking URL. Add a verified Calendly or Cal.com event link after creating the 15-minute meeting event. Do not publish a guessed or placeholder URL.
