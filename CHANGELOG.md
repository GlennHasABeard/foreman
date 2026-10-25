# Changelog

All Foreman releases. Each template has its own section, plus "All individual templates" for changes every bot gets.

## v1.1.0 (2026-10-25)
Published 2026-10-25. Each template's release notes list only its own section plus "All individual templates".


### All individual templates
- **Update notice:** each bot checks once a day for a newer Foreman release, shows the notes and asks before downloading anything.
- **Prices:** profiles attached to post reads are $0.00. A nightly billing check puts $0.010 back only if X billed more user lookups than were logged. (Not Analytics Log, which uses no X API.)
- **Spend:** own daily cap, month forecast and a weekly cost digest. Estimate next to billed when console.x.com is signed in in the bot's browser; otherwise spend shows as labeled estimates and setup says once how to turn on the billed check.
- **Refused reads:** a refused or failed read says so in words, never a quiet 0.
- **Sign-in:** the shared sign-in rules, plus a small sign-in check after a box restore before any catch-up.
- **Publishing:** one shared writable publish cache, each publish logged OK or failed.
- **Chat:** short reports with counts, notable items, cost and the page link when hosted; the full list only when not hosted or the publish failed.
- **Pages:** plain light and dark design, real buttons, Last updated in Eastern time, coral when stale. Own status line.
- **No hosting needed:** anything a page saves in KV also works by chat and saves in the bot's own files (`never show @name`, `show @name again`, `@name is talked`, `mark @name done`, `show me everything from @name`, `note @name ...`, `follow up @name on DATE`).
- **One hosted bot:** its own page is its home; follow-ups and status show there. Two or more hosted: Home shows panels only for installed bots.
- **Shared profile cache** when more than one bot is installed (off when alone).
- **Schedules:** suggested run times 20 minutes apart.
- **Page marks sync (hosted):** each bot pulls its page marks from KV at the start of every run and merges them into its own store, newest mark winning per person. Two devices saving at once keep both sets of marks, and "show again" or "pending" from either side is kept as an undo (in code: `v11_wire.before_run`, worker `mergeMarks`).
- **v1.1 pages:** every page is rebuilt in the plain light and dark design with a status line and Last updated. The previous full report stays one click away as `<page>-full.html`.
- **Install files:** each template now ships `site/publish_lists.py`, `site/pages_v11.py` and `site/HOSTING.md`, which its instructions already referred to.
- **Page text:** no semicolons in page copy.
- **Fix:** saves use a unique temp file per process, so two bots saving the same file at once can no longer fail (this was the occasional test_round3 failure).

### Follow Audit
- Live follower and following counts with an as-of time.
- Plain unfollow wording: Unfollowed you, Account gone (from the per-name lookup), followers lost.
- Newest-followers check with an adjustable size (default 350) and its cost shown.
- X's own unfollow count and Removed by X only when Analytics Log is installed; otherwise "followers lost".
- New followers tab, 4-week trend, Top risks box.
- Light-only nights skip rebuilds when full data has not changed.
- Unfollowed you and Account gone come from Follow Audit's own per-name lookup, with or without Analytics Log.
- Page: tiles, Top risks, Unfollowed you, Account gone and New followers lists with Say hi.

### Follow Finder
- Stats strip, free pre-screen before any paid check.
- Engagement-per-follower chip and sort; follows-you chip only with Follow Audit installed.
- Never show tab with undo, Returning soon from the 60-day rest.
- Language and size quotas are your own settings, off by default.
- Fix: direct profile lookups in verify mode are priced at the user rate, not the attached-profile rate.
- Page: Never show tab with Undo, engagement and follows-you chips, and a picks this run tile. Older Never show marks saved by the live Scout page (`never-scout`) are read too.

### Shoutout Picker
- Done and Pending, bench warning, grouped skip reasons, "Art type", "runner-up promoted".
- Reuses Follow Audit's follower check from the last 24 hours when installed; otherwise its own scan with the cost shown first.
- Top fans and Write shoutout only when Reply Queue or Fan Finder is installed.
- Page: Write shoutout (gated as above), Done and Pending toggles, bench warning, filters.

### Reply Queue
- Reply, Like and Open buttons. The reply draft starts empty, since X adds the @mention itself.
- Regulars by distinct conversations, Drowning posts, median time to reply (7 and 30 days, from page or chat done marks).
- Filters and sort, mentions first, runs per day as a setting (default 3).
- The 72 hour window is unchanged (a 48 hour trial on the live bots ends Nov 1).
- Page: queue cards with Reply, Like, Open and Mark done, a draft box, the Regulars chip, Drowning posts (first words of each post), filters, sort and a median time to reply tile.

### Fan Finder
- Reuses Reply Queue's pull when installed (under 12 hours old), otherwise its own pull, with pull age and cost line.
- Left out reasons with queue position, Show again and "back in N days".
- Clearer likes banner, stages and score breakdown.
- Page: stage buttons (new, engaged, talked, done), Why left out, Show again.

### Rerun Picker
- Original stats and last rerun date, "similar to #N" chip.
- Sponsor flag from your own sponsor list, empty by default.
- Angles folded into each pick, link-only chat when hosted, review of new video picks.
- Page: Quote it button, similar and sponsor chips.

### Analytics Log
- Finish card and UTC note, best time hints, followers gained per post.
- The 500K chart only on monetized accounts; thinner night pull.
- Google Sheet rows opt-in with your own sheet ID, otherwise a local CSV.
- Your week: 7-day totals with the date range (replies handled, median time to reply, shoutouts done, new followers, unfollows and Account gone, reruns used, spend against the cap), then each installed bot's last run.

### Foreman crew (Dispatch)
- Everything above for the crew's bots. Foreman builds the crew and hands off to Dispatch.
- Bot health panel on Home and one cross-bot weekly cost digest from Dispatch (crew bots do not send their own).
- Home: Customize (reorder or hide panels, saved per device and in KV when hosted), Top fans, Follow-ups due, per-person drawer with timeline, notes and follow-ups. Panels show real items (Reply Queue's top 5 with Reply and Open, Fan Finder's top 3, this week's shoutout picks with Done, Follow Audit's newest unfollows) and pack into columns on desktop. The number strip shows replies waiting, follow-ups due, new followers this week and today's spend against the cap.

## v1.0.1 (2026-10-23)

- Individual templates on the same Grok Bot computer now share one X sign-in (/workspace/x-signin/x_signin.json, owner-only, renewed under a lock). The first one signs in; later ones run `follow_watch.py signin-check` (one account read, booked to their own ledger) and reuse it. If a Foreman crew is present, they reuse its sign-in. Each bot keeps its own ledger and cap.
- New `bot_spend.py individual` marks a bot as set up from its individual template, so it stays standalone even next to a crew.
- `follow_watch.py auth` refuses when a sign-in already exists (use signin-check, or --force).
- README and guide wording fixes; Dispatch instructions restored.
- Old releases v0.1.0 to v0.3.0 removed.

## v1.0.0 (2026-10-23)

- First public release of Foreman and the seven individual bot templates.
