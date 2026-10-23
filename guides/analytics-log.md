# Analytics Log alone: setup guide

Follow this only after the owner typed "start setup" and `sh fetch_release.sh v0.3.0 --bot analytics-log` said the checksum is OK. Stop if `/workspace/foreman/.template-master` exists.

## Install
Copy `analytics-log/x_analytics.py` into `$BOTS_HOME/x-analytics`. Scripts only, never a sign-in or token file.

## Questions
Ask only these and save them in `$BOTS_HOME/x-analytics/config.json`: `has_premium`, `has_monetization`. Never fill an answer from an example or from anyone else's setup. If the owner says "you pick", offer two or three choices with a short reason each.

## Analytics Log notes
Analytics Log uses no X API and no X secrets. It needs the bot's own browser signed in to X on the analytics page. Ask the owner to open the bot's computer and sign in to X there themselves. Never ask for their password. Payouts are optional. Without monetization it writes "not available on this account".

## Cap and ledger
No X API cost, so no cap is needed. Nothing is booked.

## Self-check
Run `python3 x_analytics.py status` (no X reads). Report anything FLAGGED.

## Introduce yourself
Two or three lines: what you do, what it costs ($0 in API fees), and how to ask you things. Create a routine only if the owner asks for one.
