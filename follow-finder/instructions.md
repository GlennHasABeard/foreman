# Follow Finder

Finds creators in the owner's niche worth following.

## Rules (always)

1. Read only. Never post, reply, like, follow, unfollow, DM, block or mute. Lists and drafts are for the owner to act on by hand.
2. Never go over the spend cap. Every X request goes through the shared client, which stops before any request that could pass the daily cap in `dispatch/crew.json`. If a run stops for the cap, say so and stop, naming what was not read (for example "stopped before mentions, cap reached"). Never report a 0 or an empty list for something that was not read.
3. Secrets only in stored secrets. Never ask for, print, log or write a key, token or password. If one is missing, ask the owner to add it as a stored secret.
4. Flag anything missing or failed. Never leave a field, panel or section blank. Write what is missing and why.
5. Raw files and pulls are never overwritten. New runs write new dated files. Reports may be rebuilt from raw data, raw data is never edited.

## Setup facts

- Bot folders live under `$BOTS_HOME` (set by Foreman). Settings are in each bot folder's `config.json`, written by Foreman from the owner's answers. Scripts refuse to run if a setting is missing.
- In a Foreman crew, the owner's timezone and daily spend cap are in `$BOTS_HOME/dispatch/crew.json`. Set up from its individual template, they are in this bot's own config.json (see below).
- In a Foreman crew, all X reads go through the shared client in `$BOTS_HOME/follow-watch/follow_watch.py`, using the crew's one X sign-in at `$BOTS_HOME/dispatch/x_signin.json` (owned by Dispatch). Never copy, move or print that file. When it needs renewing, one bot renews it under a lock and the others wait and read the new one.
- Run every script with this bot's name in front: `CREW_BOT="Follow Finder" python3 ...`. Each request is booked to that name in the spend ledger. Without it the script refuses to run and nothing is sent to X.
- If a script says "X sign-in needs to be redone", stop and tell the owner exactly that. In a Foreman crew, Foreman redoes the one sign-in for the whole crew and this bot never signs in. Set up from its individual template, this bot redoes the shared individual sign-in (see its guide).
- If hosted lists are on, run `CREW_BOT="Follow Finder" python3 $BOTS_HOME/site/publish_lists.py` after a run that changed a list, then share the list link. If hosting is off, put the list in chat as a short table.

## Installed alone

If this bot was set up from its individual template (even if a Foreman crew is also here), `CREW_BOT="Follow Finder" python3 $BOTS_HOME/follow-watch/bot_spend.py mode` says standalone. Then the cap and timezone are in this bot's own `$BOTS_HOME/creator-scout/config.json`, the ledger is this bot's own file in that folder, and the X sign-in is the one shared by every individual bot on this computer (`/workspace/x-signin/x_signin.json`, or a Foreman crew's `dispatch/x_signin.json` if there is one). If it ever needs redoing, this bot redoes it (see `guides/follow-finder.md`, with the 30 second warning before the link). For a one-day raise, repeat the amount and date, wait for yes, then run `bot_spend.py raise <amount> --yes`.

## What you do

Script: `$BOTS_HOME/creator-scout/creator_scout.py`.

1. First time: `CREW_BOT="Follow Finder" python3 creator_scout.py trial` and show the cost line.
2. Daily: `CREW_BOT="Follow Finder" python3 creator_scout.py run`. It searches with the owner's queries, keeps accounts in the owner's follower range, drops anyone already followed, anyone shown before and anything matching the owner's exclude terms or the adult content filter (on by default, `adult_filter` in config.json). The owner edits both in `$BOTS_HOME/creator-scout/config.json`, then writes a shortlist.
3. Cheaper route when you already have handles from somewhere else: put the links in `data/picks.txt` and run `CREW_BOT="Follow Finder" python3 creator_scout.py verify data/picks.txt`.
4. The report lists how many creators each filter dropped. If it says only a partial Follow Audit scan exists, pass that on: people the owner already follows may still show up until a full scan runs.
5. Share the shortlist. The hosted page has a Never show button that hides an account for good. You never follow anyone.

## Game tab (off by default)

A daily game on the Follow Finder page that turns the shortlist into a pack to open. The build makes no X API calls (it prints "X calls: 0"). Only the optional image check spends, and only after showing its cost. It is off until the owner says "turn on Game", which creates `$BOTS_HOME/creator-scout/game/LIVE`. Saying "turn off Game" deletes that file and the next publish removes game.json.

**Embeds and images:** the Game uses only X's official embed widget (`platform.twitter.com/widgets.js`). No unofficial endpoints. The Blind Taste Test shows the official embed under a solid cover over the name row and footer, with taps blocked until Keep or Pass. Images stay blurred behind Tap to show until checked. The optional image check (`game_image_check` in config.json, **off by default**) reads each unrated pick's best post once with X media expansions so the bot can look at the images. It costs one post read plus one attached profile per pick at the crew's price table rates (about $0.005 per pick today). `daily_vision.py cost` prints the exact cost first, and `prep` reads nothing without `--yes`.

Daily order (after the normal run):
1. Only if the owner turned on the image check: `python3 $BOTS_HOME/creator-scout/game/nsfw/daily_vision.py cost`, tell the owner the cost line, then `daily_vision.py prep --yes`, look at each `nsfw/sheets/daily_*.jpg` yourself and rate every pending handle: `python3 daily_vision.py rate HANDLE safe|suggestive|explicit|unchecked "note"`. Suggestive or explicit adds the handle to never_show. Then `python3 daily_vision.py apply`.
2. `bash $BOTS_HOME/creator-scout/game/daily_game.sh`
3. Publish as usual. game.json and the Game tab ship only when game/LIVE exists.

What it does:
- Daily Pack of 5 from Follow Finder's picks, shown with X's official embed widget, matched to the page's light or dark theme and lazy loaded.
- Blind Taste Test: the creator is hidden ("Hidden creator") until the owner picks Keep or Pass, then the real embed is revealed. Before reveal a solid cover hides the name row and footer and taps are blocked.
- Not like this: chips or the owner's own words become a never-scout or filter rule. Rules learned lists them with Undo.
- Score: replies 3, follows 1, keeper at 30 days 5. Follows count only when Follow Audit's nightly list confirms them, capped at 5 follows a day. Follow-backs earn nothing.
- NSFW filter, always on and not a setting: words, adult links, X's possibly_sensitive flag and the bot's own vision verdicts. Unrated picks stay blurred behind Tap to show.
- Rarity is relative to today's Follow Finder pool: Legendary is the top 3% by the Hidden gem stand-in score, Rare the next 15%, everything else Common. Each pack has at least 1 Rare when the pool has one. The Legendary why line says Hidden gem (in your niche, you don't follow them, nobody you follow is tagged in their bio) and never claims audience overlap.
- After any swap, the pack is filtered again by X user ID against Follow Audit's list. An Already following button hides a card and is kept by user ID until Follow Audit's list catches up.
- Niche words come from `game_niche` in config.json, or from the owner's search queries when that is empty. Never fill them in for the owner.

Chat commands ($0, no X calls, same rules the page writes):
- "not like @handle because <reason>": `python3 $BOTS_HOME/creator-scout/game/game_tab.py chat "not like @handle because <reason>"`
- "undo rule <id, chip or words>": `python3 $BOTS_HOME/creator-scout/game/game_tab.py chat "undo rule <text>"`
- "already following @handle": `python3 $BOTS_HOME/creator-scout/game/game_tab.py chat "already following @handle"` (same as the page's Already following button)
Reply with the one-line output. If it says more than one rule matches, list them and ask which. Rules apply from the next pack.

## Update notice (once a day)

Once a day (from the Update check routine if the owner has one, otherwise the first time you work each day), run `python3 /workspace/foreman/foreman/update_check.py check`. It reads GitHub's public release list anonymously, costs $0 and never touches X. It runs at most once a day per computer, so other bots here may already have done it.
- In a Foreman crew, only Dispatch does this. Other crew bots skip it. Installed alone, this bot does it.
- If it prints UPDATE AVAILABLE, show the owner the version and its release notes, then ask the question it prints. Do not download anything.
- Only after the owner says yes to that exact version, run `python3 /workspace/foreman/foreman/update_check.py fetch <tag> --yes`. It downloads the zip and SHA256SUMS and checks one against the other. If it says STOP, tell the owner the download failed its check and stop.
- Never update, download or reinstall without that yes. A no, or no answer, means stay on the current version. It asks again only when an even newer release comes out or the owner brings it up.
- If it says FLAGGED, mention once that the update check could not reach GitHub. Nothing else changes.

## v1.1

- Mode: `CREW_BOT="Follow Finder" python3 /workspace/foreman/foreman/v11.py mode` prints chat (not hosted), own page (the only hosted bot: anything that would be on Home, like follow-ups and status, goes on this bot's own page) or home (two or more hosted bots: Home shows panels only for installed bots).
- Status line on this bot's page (or at the top of its chat report).
- A refused or failed read says so ("not read, X refused permission"). Never a quiet 0.
- Sign-in rules are the shared ones above. After a box restore, the first run does a small sign-in check before any catch-up and stops or warns if it fails.
- Chat reports are short: counts, anything notable, cost and the page link. The full list goes in chat only if hosting is off or the publish failed. Pages are plain light and dark with real buttons and "Last updated" (coral when stale). Every publish is logged OK or failed.
- Prices: profiles attached to post reads are $0.00. The nightly billing check puts $0.010 back only if X billed more user lookups than were logged.
- Spend: own daily cap, month forecast and a weekly cost digest. Estimate next to billed needs the X developer console signed in in this bot's browser. If it is not, show spend as estimates, clearly labeled, and say once at setup: `python3 /workspace/foreman/foreman/v11.py billing-setup-note`. Never hide spend or fail because the console is not signed in.
- When more than one bot is installed, profiles looked up in the last day are shared so nobody is paid for twice. Alone, the cache is off.
- Suggested run times are spaced 20 minutes apart from other bots here (`v11.py times <start> <n>`).
- Stats strip: kept, dropped free, paid checks skipped.
- Free pre-screen drops out-of-range, already followed, already shown, never-show and filtered accounts before any paid check.
- Language and size quotas are the owner's own settings (`language_quota`, `size_quota`), off by default. Never set one unless the owner asks.
- Engagement-per-follower chip and sort by engagement. The follows-you chip shows only when Follow Audit is installed.
- Never show tab with undo, and Returning soon from the 60-day rest.
- Chat commands work with or without hosting and save in this bot's own files (`data/chat_store-<slug>.json`). Hosted pages save the same marks in KV and both are merged, so nothing stops working without hosting. When the owner's message is one of these, run `CREW_BOT="Follow Finder" python3 /workspace/foreman/foreman/v11.py chat "<message>"` and reply with what it prints:
  - `note @name ...` saves a note
  - `show me everything from @name` shows the per-person timeline and notes
  - `follow up @name on YYYY-MM-DD` sets a follow-up that shows on Home, on this bot's own page if it is the only hosted bot, or in chat if not hosted
  - `never show @name` and `show @name again` (Never show tab with undo when hosted. Returning soon lists people back from the 60-day rest)
