# Analytics Log alone: setup guide

Follow this only after the owner typed "start setup" and `sh fetch_release.sh v1.1.2 --bot analytics-log` said the checksum is OK. Stop if `/workspace/foreman/.template-master` exists.

## Install
Copy `analytics-log/x_analytics.py`, `sheets_sync.py` and `replies_scorecard.py` into `$BOTS_HOME/x-analytics`. Scripts only, never a sign-in or token file.

## Questions
Ask only these and save them in `$BOTS_HOME/x-analytics/config.json`: `has_premium`, `has_monetization`. Never fill an answer from an example or from anyone else's setup. If the owner says "you pick", offer two or three choices with a short reason each.

## Analytics Log notes
Parse a pull with `x_analytics.py seal`. The manifest key is still `finished`. There is no `finish` alias. The tracker is an upsert: a re-pull for the same date updates that row. `replies_scorecard` ships **off** (`enabled: false`). Turn it on only if the owner asks. It reads the content export already pulled and costs $0.

Analytics Log uses no X API and no X secrets. It needs the bot's own browser signed in to X on the analytics page. Ask the owner to open the bot's computer and sign in to X there themselves. Never ask for their password. Payouts are optional. Without monetization it writes "not available on this account". The per-video list and the payouts list are copied only when X's list changed. An identical copy is skipped and the saved copy is kept.

## Cap and ledger
No X API cost, so no cap is needed. Nothing is booked.

## Self-check
Run `python3 x_analytics.py status` (no X reads). Report anything FLAGGED.

## Introduce yourself
Two or three lines: what you do, what it costs ($0 in API fees), and how to ask you things. Create a routine only if the owner asks for one.

## Updates

Once a day, the first time it works that day, the bot checks GitHub (free, no X reads) for a newer Foreman release. If there is one, it shows you the release notes and asks first. It never downloads or updates anything without your yes, and it checks every download against SHA256SUMS before using it.

## New in v1.1
`foreman/v11.py` stays in `/workspace/foreman/foreman` (like `update_check.py`). Never copy it elsewhere.
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
