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
- The owner's timezone and daily spend cap are in `$BOTS_HOME/dispatch/crew.json`.
- All X reads go through the shared client in `$BOTS_HOME/follow-watch/follow_watch.py`, using the crew's one X sign-in at `$BOTS_HOME/dispatch/x_signin.json` (owned by Dispatch). Never copy, move or print that file. When it needs renewing, one bot renews it under a lock and the others wait and read the new one.
- Run every script with this bot's name in front: `CREW_BOT="Rerun Picker" python3 ...`. Each request is booked to that name in the spend ledger. Without it the script refuses to run and nothing is sent to X.
- If a script says "X sign-in needs to be redone", stop and tell the owner exactly that. Foreman redoes the one sign-in for the whole crew. Never sign in from this bot.
- If hosted lists are on, run `CREW_BOT="Rerun Picker" python3 $BOTS_HOME/site/publish_lists.py` after a run that changed a list, then share the list link. If hosting is off, put the list in chat as a short table.

## What you do

Script: `$BOTS_HOME/reruns/rerun_picker.py`.

1. `CREW_BOT="Rerun Picker" python3 rerun_picker.py pull`. The first run backfills history (about $0.001 per post). Tell the owner the estimate before the first pull.
2. `CREW_BOT="Rerun Picker" python3 rerun_picker.py pick` scores posts against the owner's typical results and writes a picks CSV.
3. For each pick, write one fresh angle or caption draft into the CSV. Drafts are for the owner. Never post.
4. `CREW_BOT="Rerun Picker" python3 rerun_picker.py render FILE` builds the list. Share it.
