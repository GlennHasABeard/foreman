# Juniper Vale demo

Fake profile for screenshots. Juniper Vale, @junipervale_demo, about 2,400 followers, watercolor.
Every other account ends in `_demo`. Pages show a Demo data badge.

Regenerate from the repo root:

    python3 site/demo_juniper.py

No X calls and no Cloudflare. Do not put a real account in this folder.

The Game sample is `game.json` here only. It does not create `creator-scout/game/LIVE`,
so a normal publish still leaves the Game tab off.

Legendary labels come from Follow Finder's rarity cut. This build: @wash00_demo.
Those labels are stored as the cut returned them.

Home done marks include @inkwash_demo so a Home card can show Done.
That Done mark is {done: 1, at: 2026-11-05T15:00:00+00:00} for an inbound post at 14:18,
so the Reply Queue median is 42 min. See median.json.

Publish that page from this fixture, still with no Game LIVE flag:

    BOTS_HOME=demo/juniper/bots SITE_DIR=demo/juniper/published LISTS_DEMO=1 python3 site/publish_lists.py --dry-run

Dependencies: Python 3 standard library only. No pip packages and no network.
Run from the pack root. The command rewrites demo/juniper/html/ and
demo/juniper/html/scenarios/. It also writes gitignored local files
demo/juniper/bots/engagement/config.json and data/. Those two are not part of the pack.

Pages: index.html is Home. There is no dispatch.html.
Dispatch health is the first card on week.html, titled Dispatch.
Your week is week.html. The seven bot pages sit next to Home.
scenarios/analytics-nonmonetized/analytics-log.html hides the 500K chart.
scenarios/solo/<slug>/ is that bot alone, with a week page that lists only that bot.
The Analytics Log solo page is the nonmonetized one.
