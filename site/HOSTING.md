# Hosted lists (optional)

Lists can be hosted on Cloudflare for free so each list has a stable private link with checkboxes that sync across devices.

1. Cloudflare account (free). Store `CLOUDFLARE_ACCOUNT_ID` and an API token with Pages edit, Workers KV edit and Access edit as stored secrets `CLOUDFLARE_API_TOKEN`.
2. Create a KV namespace (any title, for example `lists-checks`). In the Pages project settings, bind it to the name `CHECKS`.
3. Create a Pages project (any name). The first `python3 publish_lists.py` deploy creates it if missing.
4. Address:
   - With a domain on Cloudflare: add a custom domain such as `lists.yourdomain.com` to the project. Pages.dev addresses then redirect to it.
   - Without a domain: use `https://<project>.pages.dev`.
5. Cloudflare Access (Zero Trust, free up to 50 users): add a self hosted application for the address above (and `*.<project>.pages.dev` for previews) with a policy that allows only the owner's email. Nothing is public.
6. Write `site/site.env` with `PAGES_PROJECT`, `LISTS_URL` and `KV_NAMESPACE_TITLE` (no secrets in this file).
7. Test locally first: `python3 publish_lists.py --dry-run`, then open `site/public/index.html`.

The look is one plain black and white template with system fonts. Page scripts kept: hide checked rows, sync checks (KV), a Lists menu to move between lists, and Never show on Follow Finder.
