# Foreman v1.2.0 patch notes

Prep notes for the next release. This pack is not tagged yet. Install links stay on the last tagged release until that tag exists.

## Off until you turn them on

- **Follow Finder Game.** Say "turn on Game" to create `creator-scout/game/LIVE`. Until then the tab is not published.
- **Shoutout rollover lookup** (`rollover_lookup`, default false). When on, one batched `users/by` drops deleted or suspended accounts before review. **About $0.01 per rollover.** Leave it off unless you want that spend.
- **Replies scorecard** (`replies_scorecard.enabled`, default false). When on, it reads the content export already pulled and costs $0. It does not turn itself on.

## Game embeds

The Daily Pack uses X's free embed widget (`platform.twitter.com/widgets.js`). Blind cards and vision sheets also read the free embed data at `cdn.syndication.twimg.com`. That path is unofficial and undocumented. It costs $0, but X can change or block it without notice. If it breaks, cards fall back to the saved post text and unrated picks stay blurred. Media expansions stay off. Nothing on this path calls a paid X or vision API.

## What each bot gained

- **Follow Audit.** Skip the daily newest-followers read when the estimate is 5 lost or fewer (`--force` overrides). Headline counts match the named rows. Sunday rollup of named unfollows from saved data. A run reuses a follower page it already read (`list_first`). `refile-gone` files accounts already marked gone, with no X call. The report has an Account gone section, a daily summary, and a run-cost line.
- **Follow Finder.** Language shares are floors, not caps. Size bands are floors after that and never push a language under its floor. Like floor applies to the shown best post. Whole-word off-topic filters. Sensitive accounts rest after 3 fails. A missing verified-impressions export is not counted as zero. The last saved file is kept when there is one.
- **Shoutout Picker.** Flagged mutuals left out or ranked last. Fresh rollovers keep last week's verdict. Week N on every pick. One extra band of 20 when the list is short. `catch-up` reads saved posts only.
- **Reply Queue.** One row per account, questions first, 24-hour mute in the browser, new chip, low-value fold, thread cards. Done marks save `{done: 1, at: time}`. Pulls read your own likes, mark items you already liked, and write a coverage block. A cap stop leads with the capped-pull line. Trial caps are generic (`apply_trial`, `log_trial`).
- **Fan Finder.** "N people still engaging who don't follow you yet (±D vs last week)". Backlog leads expire after 30 days. Every qualified lead is tracked in `leads_seen.json`. Stored likes still count when new like pulls are off.
- **Rerun Picker.** Sunday or 6-day tally pull, same-day quotes do not cool down, 2 picks per tool, `media-list`, `nudge`.
- **Analytics Log.** `seal` instead of `finish` (manifest key `finished` unchanged). Tracker upsert by date. 500K leave-window card. Scorecard off.

A capped pull shows one line: "Capped pull: skipped … (cost cap $X reached)".

Owned-read display estimates may scale by the last 7 days' billed/logged ratio, capped from 0.3 to 1.5, and keep the unscaled `est_cost_raw`. Spend caps use the unscaled rates.

## Demo profile

`python3 site/demo_juniper.py` writes `demo/juniper/`. Juniper Vale (`@junipervale_demo`, about 2,400 followers, watercolor). Other accounts end in `_demo`. Pages carry a Demo data badge. Game sample data is in that folder only. The Game tab stays off unless `creator-scout/game/LIVE` exists. The script does not call X or Cloudflare.

A live-vs-template diff cannot tell which side is newer. A row can be the live copy lagging the template.
