# X Bot Crew, set up by Foreman

A crew of small read only bots for your X account. They read your account through the official X API and hand you lists. They never post, reply, like, follow, unfollow, DM, block or mute. You do all of that yourself.

Built with Grok Bot and AI tools.

## What it is

You install one bot, Foreman. Foreman explains the crew, asks you a few questions, builds the bots you pick, tests each one and hands you a front desk bot called Dispatch. After that you talk to Dispatch.

## The bots

| Bot | What it does | Rough cost |
|---|---|---|
| Dispatch (required) | Your front desk. Runs or explains any bot, keeps the shared spend ledger, posts a daily spend line. | $0 |
| Follow Audit | Tracks followers and following. Lists inactive, dormant and gone accounts and who unfollowed. Never unfollows. | About $0.13 a day, plus about $0.65 to $1.00 per 1,000 accounts for a full scan |
| Follow Finder | Finds creators in your niche and size range worth following. Has a Never show button. | About $0.45 a run, about $13.50 a month daily |
| Shoutout Picker | Weekly list of mutuals and supporters worth a shoutout. Needs Follow Audit. | About $0.21 a week |
| Reply Queue | Sorts replies and mentions worth answering. | About $0.25 to $1.07 a run |
| Fan Finder | Finds people who engage with you but do not follow yet. | $0 when it reuses Reply Queue's pull |
| Rerun Picker | Suggests older posts worth posting again, with fresh angles. | About $0.02 a week, plus about $0.001 per post one time |
| Analytics Log | Saves your X analytics exports every day so you keep a history. Uses the browser, not the API. | $0 |

## Costs

The X API is pay per use. Rough prices are $0.001 to read one of your own posts, $0.005 for someone else's post and $0.01 for a profile lookup. The numbers above come from one real account's first week. Billed amounts came in at about 65 to 100 percent of the scripts' own estimates. With every bot on its normal schedule, expect roughly $30 to $80 a month. A light setup (Dispatch, Follow Audit light checks, Rerun Picker, Analytics Log) is a few dollars a month.

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

The scripts read these two names from the environment. Then Foreman runs the one time sign in, `python3 follow_watch.py auth`. It opens an X page in Grok Bot's browser, you click Authorize, and X sends the browser back to `http://127.0.0.1:8765/callback` on Grok Bot's computer, where the script is listening. If that page cannot be reached, Foreman uses `python3 follow_watch.py auth --paste` instead: you copy the full address the browser lands on after Authorize and give it to Foreman. It holds a one time code that only works for this sign in and expires in minutes. It is not your password or a secret. The sign in asks for these read scopes only: tweet.read, users.read, follows.read and offline.access, plus like.read if you pick Reply Queue or Fan Finder.

If hosting is on, Foreman also asks for `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` the same way. See `site/HOSTING.md`.

## Install

1. Set up your X developer app as above.
2. Give Grok Bot the message in `INSTALL_MESSAGE.txt`. It downloads the pinned release `v0.1.0` and its `SHA256SUMS` file from https://github.com/GlennHasABeard/foreman/releases/tag/v0.1.0, checks the zip with `sha256sum` and only then unzips it into `/workspace/foreman`. If the check fails, it stops. It never downloads from main. You can also run `sh foreman/fetch_release.sh v0.1.0` to do the same.
3. Foreman asks for your secrets through the stored secret request, asks only the questions your bots need and sets everything up.
4. Foreman checks the cost of every day of the week against your cap. Setup does not finish until every day fits.
5. Each bot runs a self check and introduces itself. Foreman ends with a crew summary.

## Raising the cap for one day

Some jobs, like a Follow Audit full scan, cost more than a normal day. Tell Dispatch something like "raise the cap to $2 for today". Dispatch repeats the amount and the date and waits for your yes. The raise is logged in the spend ledger and every bot honors it until midnight in your timezone. Then the normal cap is back by itself.

## Analytics Log needs the browser

Analytics Log does not use the X API. It downloads your analytics exports through Grok Bot's browser, so that browser must be signed in to your X account. Sign in once on Grok Bot's computer and the login stays. If the browser cannot run unattended, or X asks you to sign in again, the scheduled run cannot finish on its own. In that case open the chat and tell Analytics Log to run now while you are there.

## Hosting (optional)

Lists can live on a private Cloudflare Pages site behind Cloudflare Access, with checkmarks synced through Cloudflare KV. Use your own domain if you have one, otherwise a pages.dev address behind Access. The pages use one plain black and white template. See `site/HOSTING.md`. Without hosting, bots post their lists in chat.

## Rules every bot follows

1. Read only. Never post, reply, like, follow, unfollow, DM, block or mute.
2. Never go over the spend cap.
3. Secrets only in stored secrets. Never in chat, files or logs.
4. Flag anything missing or failed. Never leave it blank.
5. Raw files and pulls are never overwritten.

## Package layout

- `foreman/` Foreman's instructions and the bot catalog
- one folder per bot with its script, `instructions.md` and `routine.json`
- `site/` the list publisher and hosting guide
- `config.example.json` every setting Foreman will ask about

## License

No license is included.
