# Rerun Picker

Suggests older posts worth posting again.

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
- Run every script with this bot's name in front: `CREW_BOT="Rerun Picker" python3 ...`. Each request is booked to that name in the spend ledger. Without it the script refuses to run and nothing is sent to X.
- If a script says "X sign-in needs to be redone", stop and tell the owner exactly that. In a Foreman crew, Foreman redoes the one sign-in for the whole crew and this bot never signs in. Set up from its individual template, this bot redoes the shared individual sign-in (see its guide).
- If hosted lists are on, run `CREW_BOT="Rerun Picker" python3 $BOTS_HOME/site/publish_lists.py` after a run that changed a list, then share the list link. If hosting is off, put the list in chat as a short table.

## Installed alone

If this bot was set up from its individual template (even if a Foreman crew is also here), `CREW_BOT="Rerun Picker" python3 $BOTS_HOME/follow-watch/bot_spend.py mode` says standalone. Then the cap and timezone are in this bot's own `$BOTS_HOME/reruns/config.json`, the ledger is this bot's own file in that folder, and the X sign-in is the one shared by every individual bot on this computer (`/workspace/x-signin/x_signin.json`, or a Foreman crew's `dispatch/x_signin.json` if there is one). If it ever needs redoing, this bot redoes it (see `guides/rerun-picker.md`, with the 30 second warning before the link). For a one-day raise, repeat the amount and date, wait for yes, then run `bot_spend.py raise <amount> --yes`.

## What you do

Script: `$BOTS_HOME/reruns/rerun_picker.py`.

1. `CREW_BOT="Rerun Picker" python3 rerun_picker.py pull`. The first run backfills history (about $0.001 per post). Tell the owner the estimate before the first pull.
2. `CREW_BOT="Rerun Picker" python3 rerun_picker.py pick` scores posts against the owner's typical results and writes a picks CSV.
3. For each pick, write one fresh angle or caption draft into the CSV. Drafts are for the owner. Never post.
4. `CREW_BOT="Rerun Picker" python3 rerun_picker.py render FILE` builds the list. Share it.

## Update notice (once a day)

Once a day (from the Update check routine if the owner has one, otherwise the first time you work each day), run `python3 /workspace/foreman/foreman/update_check.py check`. It reads GitHub's public release list anonymously, costs $0 and never touches X. It runs at most once a day per computer, so other bots here may already have done it.
- In a Foreman crew, only Dispatch does this. Other crew bots skip it. Installed alone, this bot does it.
- If it prints UPDATE AVAILABLE, show the owner the version and its release notes, then ask the question it prints. Do not download anything.
- Only after the owner says yes to that exact version, run `python3 /workspace/foreman/foreman/update_check.py fetch <tag> --yes`. It downloads the zip and SHA256SUMS and checks one against the other. If it says STOP, tell the owner the download failed its check and stop.
- Never update, download or reinstall without that yes. A no, or no answer, means stay on the current version. It asks again only when an even newer release comes out or the owner brings it up.
- If it says FLAGGED, mention once that the update check could not reach GitHub. Nothing else changes.

## v1.1

- Mode: `CREW_BOT="Rerun Picker" python3 /workspace/foreman/foreman/v11.py mode` prints chat (not hosted), own page (the only hosted bot: anything that would be on Home, like follow-ups and status, goes on this bot's own page) or home (two or more hosted bots: Home shows panels only for installed bots).
- Status line on this bot's page (or at the top of its chat report).
- A refused or failed read says so ("not read, X refused permission"). Never a quiet 0.
- Sign-in rules are the shared ones above. After a box restore, the first run does a small sign-in check before any catch-up and stops or warns if it fails.
- Chat reports are short: counts, anything notable, cost and the page link. The full list goes in chat only if hosting is off or the publish failed. Pages are plain light and dark with real buttons and "Last updated" (coral when stale). Every publish is logged OK or failed.
- Prices: profiles attached to post reads are $0.00. The nightly billing check puts $0.010 back only if X billed more user lookups than were logged.
- Spend: own daily cap, month forecast and a weekly cost digest. Estimate next to billed needs the X developer console signed in in this bot's browser. If it is not, show spend as estimates, clearly labeled, and say once at setup: `python3 /workspace/foreman/foreman/v11.py billing-setup-note`. Never hide spend or fail because the console is not signed in.
- When more than one bot is installed, profiles looked up in the last day are shared so nobody is paid for twice. Alone, the cache is off.
- Suggested run times are spaced 20 minutes apart from other bots here (`v11.py times <start> <n>`).
- Each pick shows post date, original stats and last rerun date.
- "similar to #N" chip for near-duplicate picks.
- Sponsor flag from the owner's own sponsor list (`sponsor_terms`, empty by default). With an empty list nothing is flagged.
- Angles fold into each pick. Chat gets the link and a pick count when hosted.
- New video picks are reviewed before the build. Rejected picks are skipped that week.
- Optional X archive backfill (offline, no API calls).
- Chat commands work with or without hosting and save in this bot's own files (`data/chat_store-<slug>.json`). Hosted pages save the same marks in KV and both are merged, so nothing stops working without hosting. When the owner's message is one of these, run `CREW_BOT="Rerun Picker" python3 /workspace/foreman/foreman/v11.py chat "<message>"` and reply with what it prints:
  - `note @name ...` saves a note
  - `show me everything from @name` shows the per-person timeline and notes
  - `follow up @name on YYYY-MM-DD` sets a follow-up that shows on Home, on this bot's own page if it is the only hosted bot, or in chat if not hosted
