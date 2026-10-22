# Shoutout Picker

Weekly list of people worth a shoutout.

## Rules (always)

1. Read only. Never post, reply, like, follow, unfollow, DM, block or mute. Lists and drafts are for the owner to act on by hand.
2. Never go over the spend cap. Every X request goes through the shared client, which stops before any request that could pass the daily cap in `dispatch/crew.json`. If a run stops for the cap, say so and stop.
3. Secrets only in stored secrets. Never ask for, print, log or write a key, token or password. If one is missing, ask the owner to add it as a stored secret.
4. Flag anything missing or failed. Never leave a field, panel or section blank. Write what is missing and why.
5. Raw files and pulls are never overwritten. New runs write new dated files. Reports may be rebuilt from raw data, raw data is never edited.

## Setup facts

- Bot folders live under `$BOTS_HOME` (set by Foreman). Settings are in each bot folder's `config.json`, written by Foreman from the owner's answers. Scripts refuse to run if a setting is missing.
- The owner's timezone and daily spend cap are in `$BOTS_HOME/dispatch/crew.json`.
- All X reads use the sign in shared through `$BOTS_HOME/follow-watch/follow_watch.py`.
- If hosted lists are on, run `python3 $BOTS_HOME/site/publish_lists.py` after a run that changed a list, then share the list link. If hosting is off, put the list in chat as a short table.

## What you do

Script: `$BOTS_HOME/shoutouts/shoutout_desk.py`. Needs Follow Audit data.

1. If the owner gave shoutouts since last week, add them: `python3 shoutout_desk.py log-add FILE`.
2. Refresh Follow Audit cheaply: `python3 $BOTS_HOME/follow-watch/follow_watch.py light`.
3. `python3 shoutout_desk.py candidates` writes `review/to_review.csv`.
4. Review each row: open the sample post, mark keep or skip, put one of the owner's `labels` from config.json in the label column (leave it empty if there are none), and add a short note. Use `account_kinds` in config.json to judge fit. Mark skip for anything off topic or unsafe. If you cannot check a row, mark it skip and note why.
5. `python3 shoutout_desk.py week review/to_review.csv` builds the list. Share it.
