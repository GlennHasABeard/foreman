# Changes for the next release

v1.2.1 is published. v1.2.2 is a docs patch on that tree and does not change the defaults below. The v1.2.0 release stays published. Share acceptance is not claimed here.

## Shipped in this prep

### Follow Finder
- Game tab stays off until `creator-scout/game/LIVE` exists.
- Game embed uses only the official embed widget. v1.2.1 removes the unofficial embed path. Saved post text remains if an embed does not load. Unrated picks stay blurred.

### Analytics Log
- 500K leave-window card (already in the pack, covered by `tests/test_v12_leave_window.py`).
- `seal` replaces `finish`. Manifest key `finished` unchanged. No alias.
- Tracker upsert by date (`sheets_sync.plan_tracker_upsert`).
- Replies scorecard ships **off**.

### QOL rounds 5 to 8
- n01 newest-followers skip at 5 lost, with a 7-night replay. `--force` overrides.
- n02 new-follower headline equals the named rows.
- n03 Sunday rollup from saved data.
- n48 `x_prices.counts()` scales owned-read display estimates and keeps `est_cost_raw`. Caps stay unscaled.
- n23, n19, n20, n21, n22 radar new chip, questions, low-value fold, one row per account, thread rollup.
- n27 stored likes still count when new like pulls are off.
- n14 `catch-up` from saved posts.
- n09 word-boundary off-topic filters.
- n17 flagged mutuals. n13 rollover lookup **off** (about $0.01 per rollover if enabled). n32 later-local-day reruns. n31 `max_per_tool` 2.
- n10 like floor on the shown best post. n05 language floors, not caps.
- Radar Done marks `{done, at}` and `qol7_medrt` at publish.
- n12 keep-fresh rollovers. n30 `media-list`. n29 `nudge`. n52 Due today.
- n35 `seal`. n07 sensitive rest. n15 week N. n18 one extra band. n06 size-band floors.
- n26 backlog line: "N people still engaging who don't follow you yet (±D vs last week)".
- n49 capped-pull line. n38 replies scorecard **off**.
- Warm Leads `leads_expire_days` default 30.

## n55 gaps ported after the first prep commit

The diff cannot tell which side is newer. These were the live behaviors the template was still missing:

- Reply Queue pull reads the owner's likes, writes a coverage block, and leads a cap stop with the capped-pull line.
- Radar marks items already liked. `apply_trial` and `log_trial` are generic cap helpers.
- Fan Finder tracks every qualified lead in `leads_seen.json`. The backlog line stays "N people still engaging who don't follow you yet (±D vs last week)". `leads_expire_days` stays 30.
- Follow Audit reuses a page already read in the run (`list_first`), `refile-gone` uses saved data only, the report section is Account gone, and the daily check has a summary plus a run-cost line.
- A missing verified-impressions export is not zero. The last saved file is kept when one exists.

## Demo

`site/demo_juniper.py` builds the Juniper Vale demo under `demo/juniper/`. Regenerate with `python3 site/demo_juniper.py`.

## Not ported

- Private owner bots and configs listed in the box-only private exclude list stay on the live bots and are not in this pack.
- Git tag, GitHub release, and zip. Those wait until this prep is reviewed.
