# DAEMON ACE — Free lead inbox, D1 storage and booking setup

The public site stays on its existing Cloudflare Workers address. Email notifications are intentionally disabled.

## Included in the repository
- Public inquiries are stored in Cloudflare D1.
- Private dashboard at `/admin`.
- Dashboard authentication uses a Cloudflare Worker secret named `DASHBOARD_PASSWORD` and a signed, HttpOnly, Secure, SameSite=Strict cookie (12-hour session).
- Lead statuses: new, contacted, qualified and closed.
- Admin API returns up to the latest 250 inquiries.
- No lead notification emails are sent.

## Required one-time Cloudflare setup
1. Open Cloudflare Dashboard → **Workers & Pages → D1 SQL Database → Create database**.
2. Name it `daemon-ace-leads`.
3. Copy the new database's **Database ID**.
4. Edit `wrangler.toml` in GitHub. Uncomment the `[[d1_databases]]` block and replace `REPLACE_WITH_REAL_D1_DATABASE_ID` with the exact ID from Cloudflare.
5. Open the D1 database's **Console** and run all SQL from `migrations/0001_create_leads.sql`.
6. Open **Workers & Pages → daemon-it-consulting → Settings → Variables and Secrets**. Add `DASHBOARD_PASSWORD` as a **secret**. Use a long, unique password and keep it private.
7. Deploy the updated Worker using the existing Cloudflare deployment flow. Keep the Worker name `daemon-it-consulting`.
8. Check `/api/health`; after the D1 binding is active it should report `lead_storage_configured: true`.
9. Visit `/admin`, sign in, and submit a test inquiry from the public site.

Until the real D1 database ID is added, the schema is run, the password secret is set and the Worker is deployed, the public form will show a setup error rather than falsely claiming a lead was saved. These Cloudflare account actions cannot be completed from the GitHub repository.

## Free Cal.com booking link
Cal.com lists its individual plan as free forever, with one user, unlimited booking links and calendars, and unlimited meetings: https://cal.com/pricing

1. Create a free account at https://cal.com.
2. Choose your public username and connect the calendar you want to use for availability.
3. Create an event type: **DAEMON ACE — 15-Minute Introduction**, duration **15 minutes**.
4. Set your available days and times, then save.
5. Copy the public event URL (format: `https://cal.com/your-username/daemon-ace-intro`) and send me that exact URL. I will add it to the website. The public site will not publish a guessed booking URL.

## Privacy and operations
The dashboard is not in public navigation and requires its password. Keep that password private. Leads include contact information and business inquiry text; do not submit passwords, access tokens, private keys or sensitive infrastructure details. Stored fields are name, email, company, request type, inquiry text, status and timestamp. No IP address is stored. Email notifications remain off until a suitable free sending option is selected.
