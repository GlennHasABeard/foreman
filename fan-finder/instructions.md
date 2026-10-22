# Fan Finder

Finds people who engage but do not follow yet.

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

Script: `$BOTS_HOME/engagement/engagement.py` (the same script as Reply Queue, installed once).

1. `python3 engagement.py leads --pull-if-stale 12`. This reuses Reply Queue's pull and only pulls again when it is older than 12 hours.
2. Share the list with a link to each account and what they engaged with. Never follow or message anyone.
