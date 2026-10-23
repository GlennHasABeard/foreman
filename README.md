# X Bot Crew: Foreman and seven standalone bot templates

A crew of small read only bots for your X account. They read your account through the official X API and hand you lists. They never post, reply, like, follow, unfollow, DM, block or mute. You do all of that yourself.

Built with Grok Bot and AI tools.

## What it is

There are eight separate templates. All of them download from the same pinned GitHub release.

- **Foreman** sets up the whole crew. You install one bot, Foreman. It explains the crew, asks you a few questions, builds the bots you pick, tests each one and hands you a front desk bot called Dispatch. After that you talk to Dispatch. The crew shares one X sign-in, one spend ledger and one daily cap.
- **Seven individual templates**: Follow Audit, Follow Finder, Shoutout Picker, Reply Queue, Fan Finder, Rerun Picker and Analytics Log. Each one is its own template and sets itself up alone, with its own X sign-in, its own spend ledger and its own daily spend cap. See "Individual bot templates" below.

Pick one: either Foreman for the crew, or one or more individual templates. They are separate setups.

## The bots

| Bot | What it does | Rough cost |
|---|---|---|
| Dispatch (Foreman crew only) | Your front desk. Runs or explains any bot, keeps the shared spend ledger, posts a daily spend line. | $0 |
| Follow Audit | Tracks followers and following. Lists inactive, dormant and gone accounts and who unfollowed. Never unfollows. | About $0.13 a day, plus about $0.65 to $1.00 per 1,000 accounts for a full scan |
| Follow Finder | Finds creators in your niche and size range worth following. Has a Never show button. | About $0.45 a run, about $13.50 a month daily |
| Shoutout Picker | Weekly list of mutuals and supporters worth a shoutout. Needs Follow Audit. | About $0.21 a week |
| Reply Queue | Sorts replies and mentions worth answering. | About $0.25 to $1.07 a run |
| Fan Finder | Finds people who engage with you but do not follow yet. | $0 when it reuses Reply Queue's pull |
| Rerun Picker | Suggests older posts worth posting again, with fresh angles. | About $0.02 a week, plus about $0.001 per post one time |
| Analytics Log | Saves your X analytics exports every day so you keep a history. Uses the browser, not the API. | $0, no API cost |

## Costs

The X API is pay per use. Every bot and the spend ledger use one price table, `follow-audit/x_prices.py`, so a bot's own estimate and the ledger always agree. Run `python3 x_prices.py` to see it.

| What is read | Price each |
|---|---|
| Your own data: your posts, mentions, likes, followers, following and the likers of your posts | $0.001 |
| Other people's posts: search, quote posts, someone else's posts | $0.005 |
| A profile lookup, or a profile attached to a post | $0.010 |

Check the table against the X developer console after the first days. If X bills a kind of read at a different rate, change it in that one file. The numbers above come from one real account's first week. Billed amounts came in at about 65 to 100 percent of the scripts' own estimates. With every bot on its normal schedule, expect roughly $30 to $80 a month. A light setup (Dispatch, Follow Audit light checks, Rerun Picker, Analytics Log) is a few dollars a month.

You set a daily spend cap. All bots share it. Any request that could push the day past the cap is stopped before it is sent. Check the X developer console for what you were actually billed.

Hosting on Cloudflare is free. A domain is optional and costs about $12 a year.

## Set up your X developer app

Do this once before installing. Only you can do it, in your own X developer account.

1. Go to console.x.com and sign in with the X account the bots will read.
2. Set up billing as pay per use and add a small amount of credit. The bots only spend from this.
3. Create a new app (Projects and Apps, then create app). Any name works.
4. Open the app's settings and find User authentication settings. Click Set up.
5. App permissions: choose Read. Read only is enough. The bots never ask for write access.
6. Type of App: choose Web App, Automated App or Bot. This gives you a client secret, which the scripts use.
7. Callback URI / Redirect URL: enter exactly `http://127.0.0.1:8765/callback`
8. Website URL: any page that is yours, for example `https://x.com/yourhandle`
9. Save. X shows an OAuth 2.0 Client ID and Client Secret. Keep that page open. Do not paste them in chat.
10. Ignore the API Key, API Secret and Bearer Token on the Keys and tokens page. The bots do not use them.

Where the secrets go. When Foreman asks, it sends you a stored secret request. Put the values there, never in chat:

| Stored secret name | Value from the X console |
|---|---|
| `X_CLIENT_ID` | OAuth 2.0 Client ID |
| `X_CLIENT_SECRET` | OAuth 2.0 Client Secret |

The scripts read these two names from the environment and never write them to a file. Then Foreman runs the one time sign in, once for the whole crew, `CREW_BOT="Foreman" python3 follow_watch.py auth`.

Main path. Foreman opens an X page in Grok Bot's own browser. You click Authorize there. X sends that browser back to `http://127.0.0.1:8765/callback` on Grok Bot's computer, where the script is already listening, and the sign in finishes by itself. Nothing to copy.

Backup, only if that page cannot load, for example when you approve on your phone. Before Foreman sends the link it tells you: you have about 30 seconds after you approve. Get ready first. Click Authorize, copy the full address from the address bar of the page that will not load, and paste it to Foreman at once. Do not stop to read the page. Foreman hands it straight to the waiting script (`follow_watch.py auth-paste`), which swaps it for the sign in the moment it arrives. In our own test the first paste came too late and the second one worked.

If X says the code expired, nothing is broken. Ask Foreman for a new link and try again, a little faster. The code only works for this sign in. It is not your password or a secret. The sign in asks for these read scopes only: tweet.read, users.read, follows.read and offline.access, plus like.read if you pick Reply Queue or Fan Finder.

One sign in, shared. The sign in is saved once, in Dispatch's folder (`dispatch/x_signin.json`, readable only by its owner), and every bot uses that one file. No bot keeps its own copy and nothing ever copies it. When it needs renewing, one bot renews it under a lock while the others wait and then read the new one. If a renewal fails, the bot stops and says "X sign-in needs to be redone", and Foreman runs the sign in again.

A second sign in to the same X app cancels the first. That is why the whole crew shares one sign in. It also means a test crew needs its own X app. If you sign a test crew in to the same app your live crew uses, your live bots lose their sign in.

Every bot books its own reads. Each script runs with the bot's name (`CREW_BOT="Reply Queue"` and so on) and refuses to run without it, so the spend ledger shows what each bot spent. Each request is written to the ledger, under a lock, before the next one is sent. If the daily cap stops a bot, its result says so, for example "stopped before mentions, cap reached", never a 0 that looks real.

What each bot says when a cap stops it:

- Reply Queue reads your mentions and quotes first and your likes last. If the mentions were not read, it says so, and the count is missing, not zero. If your likes were not finished, it keeps every item and marks the ones it could not check "may already be liked".
- Fan Finder warns when the pull it uses stopped on the cap, so a low count is not a real count.
- Follow Finder lists how many creators each filter dropped. If only a partial Follow Audit scan exists, it says so and explains that people you already follow may still show up until a full scan runs.

If hosting is on, Foreman also asks for `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` the same way. See `site/HOSTING.md`.

## Install the Foreman template (whole crew)

1. Set up your X developer app as above.
2. Give Grok Bot the message in `INSTALL_MESSAGE.txt`. It downloads the pinned release `v1.0.0` and its `SHA256SUMS` file from https://github.com/GlennHasABeard/foreman/releases/tag/v1.0.0, checks the zip with `sha256sum` and only then unzips it into `/workspace/foreman`. If the check fails, it stops. It never downloads from main. You can also run `sh foreman/fetch_release.sh v1.0.0` to do the same.
3. Foreman asks for your secrets through the stored secret request, asks only the questions your bots need and sets everything up.
4. Foreman checks the cost of every day of the week against your cap. Setup does not finish until every day fits.
5. Each bot runs a self check and introduces itself. Foreman ends with a crew summary.

## Raising the cap for one day

Some jobs, like a Follow Audit full scan, cost more than a normal day. In a Foreman crew, tell Dispatch something like "raise the cap to $2 for today". Dispatch repeats the amount and the date and waits for your yes. The raise is logged in the spend ledger and every bot honors it until midnight in your timezone. Then the normal cap is back by itself. An individual template does the same for its own cap: it repeats the amount and date, waits for your yes and runs `bot_spend.py raise`.

## Analytics Log needs the browser

Analytics Log does not use the X API, so it has no API cost and books nothing to the spend ledger. It downloads your analytics exports through Grok Bot's browser, so that browser must be signed in to your X account. Sign in once on Grok Bot's computer and the login stays. If the browser cannot run unattended, or X asks you to sign in again, the scheduled run cannot finish on its own. In that case open the chat and tell Analytics Log to run now while you are there.

## Hosting (optional)

Lists can live on a private Cloudflare Pages site behind Cloudflare Access, with checkmarks synced through Cloudflare KV. Use your own domain if you have one, otherwise a pages.dev address behind Access. The pages use one plain black and white template. See `site/HOSTING.md`. Without hosting, bots post their lists in chat.

## Rules every bot follows

1. Read only. Never post, reply, like, follow, unfollow, DM, block or mute.
2. Never go over the spend cap.
3. Secrets only in stored secrets. Never in chat, files or logs.
4. Flag anything missing or failed. Never leave it blank.
5. Raw files and pulls are never overwritten.

## Individual bot templates

Each of the seven bots is also its own template. Give a fresh Grok Bot the bot's template description. It waits until you type "start setup" and does nothing before that. Then it runs `sh foreman/fetch_release.sh v1.0.0 --bot <slug>`, which downloads the pinned release and SHA256SUMS, checks them and unzips only that bot's files into `/workspace/foreman`. The list of files per bot is in `foreman/standalone.json`. Each bot has a short setup guide in `guides/<slug>.md`.

How an individual template handles money and sign-in:

- It has its own daily spend cap and its own ledger in its own folder. The one-day raise works with `bot_spend.py raise`. It ends at midnight in your timezone by itself.
- It does its own X sign-in and saves it in its own folder, renewed under a lock.
- A second sign-in to the same X app cancels the first. If you set up more than one individual template, give each one its own X app so they do not knock each other out.
- Install an individual template under its own `BOTS_HOME`, not inside a Foreman crew's folder.
- You see the cost before anything paid runs.

| Bot | Files (inside foreman/) | Secrets | X scopes | Browser | Works with |
|---|---|---|---|---|---|
| Follow Audit | `follow-audit/follow_watch.py`, `follow-audit/x_prices.py`, `follow-audit/bot_spend.py`, `follow-audit/instructions.md`, `follow-audit/routine.json` | X_CLIENT_ID, X_CLIENT_SECRET | tweet.read, users.read, follows.read, offline.access | no | nothing else |
| Follow Finder | `follow-audit/follow_watch.py`, `follow-audit/x_prices.py`, `follow-audit/bot_spend.py`, `follow-finder/creator_scout.py`, `follow-finder/instructions.md`, `follow-finder/routine.json` | X_CLIENT_ID, X_CLIENT_SECRET | tweet.read, users.read, follows.read, offline.access | no | follow-audit (optional, for follows-you marks) |
| Shoutout Picker | `follow-audit/follow_watch.py`, `follow-audit/x_prices.py`, `follow-audit/bot_spend.py`, `shoutout-picker/shoutout_desk.py`, `shoutout-picker/instructions.md`, `shoutout-picker/routine.json` | X_CLIENT_ID, X_CLIENT_SECRET | tweet.read, users.read, follows.read, offline.access | no | follow-audit (optional, or its own follower scan) |
| Reply Queue | `follow-audit/follow_watch.py`, `follow-audit/x_prices.py`, `follow-audit/bot_spend.py`, `reply-queue/engagement.py`, `reply-queue/instructions.md`, `reply-queue/routine.json` | X_CLIENT_ID, X_CLIENT_SECRET | tweet.read, users.read, follows.read, offline.access, like.read | no | nothing else |
| Fan Finder | `follow-audit/follow_watch.py`, `follow-audit/x_prices.py`, `follow-audit/bot_spend.py`, `reply-queue/engagement.py`, `fan-finder/instructions.md`, `fan-finder/routine.json` | X_CLIENT_ID, X_CLIENT_SECRET | tweet.read, users.read, follows.read, offline.access, like.read | no | reply-queue (optional, reuses its pull) |
| Rerun Picker | `follow-audit/follow_watch.py`, `follow-audit/x_prices.py`, `follow-audit/bot_spend.py`, `rerun-picker/rerun_picker.py`, `rerun-picker/instructions.md`, `rerun-picker/routine.json` | X_CLIENT_ID, X_CLIENT_SECRET | tweet.read, users.read, follows.read, offline.access | no | nothing else |
| Analytics Log | `analytics-log/x_analytics.py`, `analytics-log/instructions.md`, `analytics-log/routine.json` | none | none | yes, signed in to X | nothing else |

Every bot also gets `README.md`, `LICENSE`, `config.example.json`, `foreman/standalone.json`, `foreman/fetch_release.sh` and its own `guides/<slug>.md`.

Bot by bot notes:

- Shoutout Picker without Follow Audit offers its own follower scan, with the cost shown first, or installing Follow Audit.
- Fan Finder without Reply Queue makes its own pull and tells you it costs about the same as one Reply Queue run.
- Analytics Log uses no X API and no secrets. It needs the bot's browser signed in to X, which you do yourself.
- Follow Audit's script is in every X bot's files because it holds the X client, the cap and the sign-in code each bot uses.

## Package layout

- `foreman/` Foreman's instructions and the bot catalog
- one folder per bot with its script, `instructions.md` and `routine.json`
- `guides/` one short setup guide per individual template
- `foreman/standalone.json` and `foreman/fetch_release.sh` the individual template file lists and the download script
- `site/` the list publisher and hosting guide
- `config.example.json` every setting Foreman will ask about

## License

MIT License. Copyright (c) 2026 Glenn Williams. See `LICENSE`.
