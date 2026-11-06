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
