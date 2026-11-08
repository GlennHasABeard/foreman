# Analytics Log alone: setup guide

Follow this only after the owner typed "start setup" and `sh /workspace/foreman/foreman/fetch_release.sh v1.2.3 --bot analytics-log` said the checksum is OK. Stop if `/workspace/foreman/.template-master` exists. If `/workspace/foreman` already exists, ask before replacing it.

## Rules (always)

1. Read only on X: never post, reply, like, follow, unfollow, DM, block or mute. Stay out of X Chat.
2. Never go over the daily spend cap. Book every request in the ledger before the next. If the cap stops a run, say what was not read.
3. Secrets only in stored secrets. Never ask for, print or write a key, token or password in chat or files.
4. Flag anything missing or failed. Never report a fake 0 or empty list for something not read.
5. Never overwrite raw files or pulls; new runs write new dated files.

No memory, routines or secrets until setup is finished.


## Install
Copy `analytics-log/x_analytics.py`, `sheets_sync.py` and `replies_scorecard.py` into `$BOTS_HOME/x-analytics`. Scripts only, never a sign-in or token file.

## Questions
Ask only these and save them in `$BOTS_HOME/x-analytics/config.json`: `has_premium`, `has_monetization`. Never fill an answer from an example or from anyone else's setup. If the owner says "you pick", offer two or three choices with a short reason each.

## Analytics Log notes
Parse a pull with `python3 $BOTS_HOME/x-analytics/x_analytics.py seal`. The manifest key is still `finished`. There is no `finish` alias. The tracker is an upsert: a re-pull for the same date updates that row. `replies_scorecard` is **on** by default and costs $0. It reads the content export already pulled. Set `enabled` to false only if the owner asks. The Sunday routine is offered in Routines and is created only after the owner says yes.

Analytics Log uses no X API and no X secrets. It needs the bot's own browser signed in to X on the analytics page. Ask the owner to open the bot's computer and sign in to X there themselves. Never ask for their password. Payouts are optional. Without monetization it writes "not available on this account". The per-video list and the payouts list are copied only when X's list changed. An identical copy is skipped and the saved copy is kept.

## Cap and ledger
No X API cost, so no cap is needed. Nothing is booked. This bot makes no paid X request. If a paid request is ever added, book it in the ledger before the next one, and if the cap stops a run, say what was not read.

## Self-check
Run `python3 $BOTS_HOME/x-analytics/x_analytics.py status` (no X reads). Report anything FLAGGED. Never report a fake 0 or empty list for something that was not read.

## Routines

Offer each routine below. Say what it is for and what it costs. Create it only after the owner says yes to that routine. Never create a routine they did not accept.

- Nightly pull. Saves that day's analytics export through the browser. $0 in API fees.
- Weekly replies scorecard. Sunday run of `python3 $BOTS_HOME/x-analytics/x_analytics.py scorecard`. It reads the content export already pulled and costs $0. The scorecard setting can stay on. This routine is still not created until the owner says yes.
- Update check. Once a day, `python3 /workspace/foreman/foreman/update_check.py check`. $0. It does not download a release.

## Introduce yourself
Two or three lines: what you do, what it costs ($0 in API fees), and how to ask you things. Name only the routines the owner accepted.

## Updates

Before any version change, run `python3 /workspace/foreman/foreman/update_check.py check`. It reads GitHub's public release list, costs $0, and does not touch X. If it prints UPDATE AVAILABLE, show the owner the version and the release notes, then ask. Do not download yet. Only after the owner says yes to that exact version, run `python3 /workspace/foreman/foreman/update_check.py fetch <tag> --yes`. That downloads the zip and SHA256SUMS and checks one against the other. If it says STOP, tell the owner and stop. A no, or no answer, means stay on this version. Never download from main. The zip does not carry its own digest. The check uses the SHA256SUMS file published beside that release.


## New in v1.1
`foreman/v11.py` and `foreman/v11_wire.py` stay in `/workspace/foreman/foreman` (like `update_check.py`). Never copy them elsewhere. `python3 /workspace/foreman/foreman/v11_wire.py` rebuilds a bot's saved panel and does not call the X API.
- If your lists are hosted, marks you make on the page (never show, show again, done, stages, notes, follow-ups) are pulled into the bot before every run, so the page and chat always agree. The newest mark wins, and two devices saving at once keep both. The previous full report stays linked at the bottom of each page.
- No hosting needed: every saved mark works by chat and lives in this bot's own files.
  - `note @name ...` saves a note
  - `show me everything from @name` shows the per-person timeline and notes
  - `follow up @name on YYYY-MM-DD` sets a follow-up that shows on Home, on this bot's own page if it is the only hosted bot, or in chat if not hosted
- One hosted bot: its own page is its home, and follow-ups show there.

What this bot got in v1.1:
- Finish card checks the pull behind the scenes and only speaks up when something is off, with a short UTC note.
- Best time of day hints and followers gained per post.
- The 500K window chart shows only on monetized accounts.
- Thinner night pull: audience, 1-year video and heatmap move to the weekly night pull.
- Google Sheet rows are opt-in: only when the owner gives their own sheet ID (`sheet_id`). Otherwise rows go to a local CSV.
- Your week on X: sections only for the bots installed (alone: impressions and followers).
