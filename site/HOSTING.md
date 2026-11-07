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

Screenshot fixture, no network: `python3 site/demo_juniper.py` writes `demo/juniper/` for Juniper Vale (`@junipervale_demo`). It does not create the Game LIVE flag.

The look is one plain black and white template with system fonts. Page scripts kept: hide checked rows, sync checks (KV), a Lists menu to move between lists, and Never show on Follow Finder.

## v1.1

Home shows panels only for installed bots. With one hosted bot there is no Home: that bot's page is home and gets follow-ups and its status line. Without hosting, every KV feature works by chat and saves in the bot's own files (see each guide). Pages use `foreman/v11.py` page design: plain light and dark, real buttons, Last updated in coral when stale.

## Game tab (off by default)
Off unless `creator-scout/game/LIVE` exists. When on, publish copies `game/live/game.json` to the site and adds the Game tab to the final `follow-finder.html`. Its marks use the same `CHECKS` KV binding (pages `game-rules`, `game-binder`, `game-taste`, `game-pending`, `game-following`). When off, publish deletes `game.json` from the site.
**Embeds and images:** the Game stays off until the owner says "turn on Game". The Daily Pack uses only X's official embed widget (`platform.twitter.com/widgets.js`). If an embed does not load, the card shows the saved post text. Unrated picks stay blurred. The optional image check (`game_image_check`, **off by default**) uses official media expansions, shows its cost first, and reads nothing without `--yes`.
