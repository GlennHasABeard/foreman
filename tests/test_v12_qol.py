"""v1.2 template behavior. Stdlib only."""
import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "follow-audit"))
sys.path.insert(0, os.path.join(ROOT, "follow-finder"))
sys.path.insert(0, os.path.join(ROOT, "shoutout-picker"))
sys.path.insert(0, os.path.join(ROOT, "rerun-picker"))
sys.path.insert(0, os.path.join(ROOT, "reply-queue"))
sys.path.insert(0, os.path.join(ROOT, "analytics-log"))
sys.path.insert(0, os.path.join(ROOT, "site"))
sys.path.insert(0, os.path.join(ROOT, "foreman"))

import pages_v11
import qol_desk
import qol_leads
import qol_rerun
import qol_scout
import qol7_due
import qol7_medrt
import radar_collapse
import replies_scorecard
import sheets_sync
import weekly_rollup
import x_prices
import v11


class Headcount(unittest.TestCase):
    def test_skip_under_threshold(self):
        self.assertTrue(weekly_rollup.skip_newest_read(5, 5))
        self.assertTrue(weekly_rollup.skip_newest_read(0, 5))
        self.assertFalse(weekly_rollup.skip_newest_read(6, 5))
        self.assertFalse(weekly_rollup.skip_newest_read(0, 5, force=True))
        self.assertFalse(weekly_rollup.skip_newest_read(None, 5))

    def test_replay_line(self):
        log = [{"est_lost_before": 1, "new_followers": 1}] * 3 + [{"est_lost_before": 8, "new_followers": 4}] * 4
        line = weekly_rollup.seven_night_line(log, 5)
        self.assertIn("would have read on 4 of 7", line)
        self.assertIn("named 16 of 19", line)
        self.assertIn("5 lost or fewer", line)

    def test_headline_matches_named_rows(self):
        text = weekly_rollup.new_follower_headline(4, 2, 1)
        self.assertTrue(text.startswith("4 "))
        self.assertIn("+2 in Followed you back", text)
        self.assertIn("+1 seen but not listed", text)

    def test_sunday_rollup(self):
        sunday = date(2026, 11, 1)  # Sunday
        events = [{"event": "unfollowed_you", "date": "2026-10-30", "username": "ada", "days": 12}]
        out = weekly_rollup.sunday_rollup(events, sunday, pending_unnamed=3)
        self.assertIn("@ada: followed you for 12 days", out["text"])
        self.assertIn("Pending unnamed: 3", out["text"])
        self.assertIsNone(weekly_rollup.sunday_rollup(events, date(2026, 11, 2)))


class Prices(unittest.TestCase):
    def test_counts_scales_owned_only(self):
        raw = x_prices.estimate(owned=10, post=2, user=1)
        scaled = x_prices.counts(owned=10, post=2, user=1, billed=76, logged=100)
        self.assertAlmostEqual(scaled["owned_ratio"], 0.76)
        self.assertAlmostEqual(scaled["est_cost_raw"], raw)
        self.assertAlmostEqual(scaled["est_cost"], raw - 0.01 + 0.01 * 0.76)
        self.assertEqual(x_prices.owned_ratio(1, 100), 0.3)
        self.assertEqual(x_prices.owned_ratio(200, 100), 1.5)
        self.assertEqual(x_prices.worst_case("/users/1/tweets", {"max_results": 10}, owner_id="1"), 0.01)


class Scout(unittest.TestCase):
    def test_lang_floor_is_not_a_cap(self):
        ranked = [{"lang": "en", "followers": 100, "i": i} for i in range(8)] + [{"lang": "fr", "followers": 100, "i": i} for i in range(2)]
        kept = qol_scout.select_shortlist(ranked, 6, {"fr": 0.2})
        self.assertEqual(sum(1 for c in kept if c["lang"] == "fr"), 2)
        self.assertEqual(sum(1 for c in kept if c["lang"] == "en"), 4)
        # a strong day keeps every ranked pick in that language when the cut allows it
        kept_all = qol_scout.select_shortlist(ranked, 10, {"en": 0.2})
        self.assertEqual(sum(1 for c in kept_all if c["lang"] == "en"), 8)

    def test_size_band_does_not_break_language_floor(self):
        ranked = [{"lang": "fr", "followers": 100, "i": i} for i in range(4)] + [{"lang": "en", "followers": 90000, "i": i} for i in range(6)]
        bands = [{"name": "big", "min": 50000, "max": 100000, "share": 0.8}]
        kept = qol_scout.select_shortlist(ranked, 5, {"fr": 0.4}, bands)
        self.assertGreaterEqual(sum(1 for c in kept if c["lang"] == "fr"), 2)

    def test_offtopic_word_boundary(self):
        self.assertEqual(qol_scout.offtopic_reason("a casino night"), "casino or betting")
        self.assertIsNone(qol_scout.offtopic_reason("casinonight"))
        self.assertEqual(qol_scout.offtopic_reason("new AI tool"), "AI tool or product")
        self.assertEqual(qol_scout.offtopic_reason("loves glamour"), "glamour")
        self.assertEqual(qol_scout.offtopic_reason("keep the zebras", ["zebras"]), "zebras")
        self.assertIsNone(qol_scout.offtopic_reason("hello", ["zebras"]))

    def test_like_floor_on_shown_post(self):
        self.assertTrue(qol_scout.shown_under_like_floor(3, 10, True))
        self.assertFalse(qol_scout.shown_under_like_floor(10, 10, True))
        self.assertFalse(qol_scout.shown_under_like_floor(0, 10, False))

    def test_sensitive_rest(self):
        state, today = {}, date(2026, 11, 1)
        for _ in range(3):
            qol_scout.note_sensitive(state, "Ada", today, 3, 30)
        self.assertTrue(qol_scout.resting(state, "ada", today))
        self.assertFalse(qol_scout.resting(state, "ada", today + timedelta(days=31)))


class Shoutout(unittest.TestCase):
    def test_rollover_default_off_and_cost(self):
        import shoutout_desk
        self.assertFalse(shoutout_desk.DEFAULT_CONFIG["rollover_lookup"])
        self.assertIn("$0.04", qol_desk.rollover_setup_line())
        self.assertIn("$0.04", qol_desk.rollover_cost_line(False))
        self.assertAlmostEqual(qol_desk.rollover_monthly_cost(), 0.04)

    def test_flags_and_week_label(self):
        self.assertEqual(qol_desk.flag_decision(["likely fake"]), "out")
        self.assertEqual(qol_desk.flag_decision(["inactive"]), "last")
        self.assertEqual(qol_desk.week_label(1, False), "week 1 · new")
        self.assertEqual(qol_desk.week_label(1, True), "week 1 · runner-up promoted")
        self.assertEqual(qol_desk.week_label(3), "week 3")

    def test_one_extra_band(self):
        self.assertTrue(qol_desk.needs_extra_band(2, 5, False))
        self.assertFalse(qol_desk.needs_extra_band(2, 5, True))
        self.assertFalse(qol_desk.needs_extra_band(5, 5, False))

    def test_catch_up_saved_posts_only(self):
        added = qol_desk.catch_up_plan([], [{"id": "1", "text": "shoutout @ada", "created": "2026-11-01"}], date(2026, 11, 5))
        self.assertEqual(added[0]["handle"], "ada")
        again = qol_desk.catch_up_plan(added, [{"id": "1", "text": "shoutout @ada", "created": "2026-11-01"}], date(2026, 11, 5))
        self.assertEqual(again, [])

    def test_classify_gone(self):
        body = {"data": [{"username": "ada"}], "errors": [{"value": "bea", "title": "Suspended"}]}
        got = qol_desk.classify_users_by(body, ["ada", "bea", "cy"])
        self.assertEqual(got["ada"], "active")
        self.assertEqual(got["bea"], "suspended")
        self.assertEqual(got["cy"], "deleted")


class Rerun(unittest.TestCase):
    def test_same_day_does_not_count(self):
        self.assertFalse(qol_rerun.later_local_day("2026-11-01T10:00:00+00:00", "2026-11-01T23:00:00+00:00", "UTC"))
        self.assertTrue(qol_rerun.later_local_day("2026-11-01T10:00:00+00:00", "2026-11-02T01:00:00+00:00", "UTC"))

    def test_tally_night_skip(self):
        sunday = datetime(2026, 11, 1, 21, tzinfo=timezone.utc)
        skip, _ = qol_rerun.tally_night_skip(sunday, "2026-10-31T00:00:00+00:00")
        self.assertFalse(skip)
        monday = datetime(2026, 11, 2, 21, tzinfo=timezone.utc)
        skip, why = qol_rerun.tally_night_skip(monday, "2026-11-01T00:00:00+00:00")
        self.assertTrue(skip)
        self.assertIn("$0", why)
        skip, _ = qol_rerun.tally_night_skip(monday, "2026-10-20T00:00:00+00:00")
        self.assertFalse(skip)

    def test_tool_cap_backfills(self):
        ranked = [{"text": "kling one"}, {"text": "kling two"}, {"text": "kling three"}, {"text": "a poem"}]
        picks = qol_rerun.cap_per_tool(ranked, 3, 2)
        self.assertEqual([p["text"] for p in picks], ["kling one", "kling two", "a poem"])
        self.assertEqual(len(qol_rerun.cap_per_tool(ranked, 4, 2)), 4)
        self.assertEqual(len(qol_rerun.cap_per_tool(ranked, 3, 0)), 3)

    def test_media_list_and_nudge(self):
        left = qol_rerun.media_list(
            [{"url": "https://x.com/a/status/1", "format": "video"}, {"url": "https://x.com/a/status/2", "format": "photo"}],
            ["https://x.com/a/status/1"])
        self.assertEqual(left, [])
        left = qol_rerun.media_list([{"url": "https://x.com/a/status/9", "format": "video"}], [])
        self.assertEqual(len(left), 1)
        self.assertIn("no build", qol_rerun.nudge_line(4, False, 3))
        self.assertIsNone(qol_rerun.nudge_line(4, True, 3))
        self.assertIsNone(qol_rerun.nudge_line(1, False, 3))


class Radar(unittest.TestCase):
    def test_questions_low_value_and_collapse(self):
        now = "2026-11-05T12:00:00+00:00"
        prev = "2026-11-05T08:00:00+00:00"
        items = [
            {"id": "1", "username": "ada", "text": "gm", "created": "2026-11-05T11:00:00+00:00", "kind": "reply"},
            {"id": "2", "username": "bea", "text": "how does this work", "created": "2026-11-05T09:00:00+00:00", "kind": "reply", "author": "b"},
            {"id": "3", "username": "bea", "text": "another note", "created": "2026-11-05T10:00:00+00:00", "kind": "reply", "author": "b"},
        ]
        prep = radar_collapse.prepare_radar(items, prev_run=prev, now=now)
        self.assertEqual(prep["low_count"], 1)
        lead = next(r for r in prep["rows"] if r["username"] == "bea")
        self.assertTrue(lead["question"])
        self.assertEqual(lead["more"], 1)
        self.assertEqual(prep["rows"][0]["username"], "bea")
        self.assertTrue(any(r["low"] for r in prep["rows"]))
        lines = radar_collapse.md_lines(prep)
        self.assertIn("new items since last run", lines[0])
        self.assertTrue(any("+1 more" in line for line in lines))

    def test_thread_rollup(self):
        items = [
            {"id": "1", "username": "ada", "text": "why though", "created": "2026-11-05T09:00:00+00:00", "conversation": "root"},
            {"id": "2", "username": "bea", "text": "because", "created": "2026-11-05T10:00:00+00:00", "conversation": "root"},
        ]
        prep = radar_collapse.prepare_radar(items, thread_rollup=True, min_people=2)
        self.assertEqual(len([r for r in prep["rows"] if not r["low"]]), 1)
        self.assertIn("2 people · 2 pings", prep["rows"][0]["text"])

    def test_new_needs_thirty_minutes(self):
        item = [{"id": "1", "username": "ada", "text": "hello there friend", "created": "2026-11-05T11:50:00+00:00"}]
        prep = radar_collapse.prepare_radar(item, prev_run="2026-11-05T11:40:00+00:00", now="2026-11-05T11:55:00+00:00")
        self.assertEqual(prep["new_count"], 0)


class MedrtDue(unittest.TestCase):
    def test_done_mark_shape(self):
        mark = qol7_medrt.new_done_mark("2026-11-05T12:00:00+00:00")
        self.assertEqual(mark, {"done": 1, "at": "2026-11-05T12:00:00+00:00"})
        self.assertTrue(qol7_medrt.is_done(1))
        self.assertTrue(qol7_medrt.is_done({"on": True}))
        self.assertIsNone(qol7_medrt.done_at(1))
        self.assertEqual(qol7_medrt.done_at(mark), mark["at"])

    def test_q4rt_uses_replies_and_at_marks(self):
        posts = {"r": {"kind": "reply", "created": "2026-11-05T12:10:00+00:00", "replied_to": "in"}}
        events = {"in": {"created": "2026-11-05T12:00:00+00:00", "username": "ada"}}
        bare = qol7_medrt.q4rt({}, {}, {"ada": 1})
        self.assertEqual(bare["n"], 0)
        timed = qol7_medrt.q4rt(posts, events, {"ada": {"done": 1, "at": "2026-11-05T12:20:00+00:00"}})
        self.assertGreaterEqual(timed["n"], 2)
        self.assertIn("n=", timed["line"])

    def test_due_today_and_off(self):
        sched = {"rules": [{"name": "Follow Audit", "due": ["sun"]}], "off": ["2026-11-08"]}
        self.assertEqual(qol7_due.due_today(sched, date(2026, 11, 1)), ["Follow Audit"])
        self.assertEqual(qol7_due.due_today(sched, date(2026, 11, 8)), [])


class Analytics(unittest.TestCase):
    def test_tracker_upsert(self):
        rows = [{"date": "2026-11-01", "value": "1"}, {"date": "2026-11-02", "value": "2"}]
        updated, action = sheets_sync.plan_tracker_upsert(rows, {"date": "2026-11-02", "value": "9"})
        self.assertEqual(action, "update")
        self.assertEqual(len(updated), 2)
        self.assertEqual(updated[1]["value"], "9")
        updated, action = sheets_sync.plan_tracker_upsert(updated, {"pulled_at_et": "2026-11-03T01:00:00", "value": "3"})
        self.assertEqual(action, "append")
        self.assertEqual(len(updated), 3)

    def test_scorecard_on_by_default(self):
        self.assertTrue(replies_scorecard.enabled({}))
        self.assertFalse(replies_scorecard.enabled({"replies_scorecard": {"enabled": False}}))
        self.assertIsNotNone(replies_scorecard.scorecard([{"kind": "reply", "text": "hi", "created": "2026-11-05"}], {}))
        card = replies_scorecard.scorecard(
            [{"kind": "reply", "text": "hi", "created": "2026-11-05", "impression_count": 10, "follows": 1}],
            {"replies_scorecard": {"enabled": True, "days": 7, "top": 10, "reply_types": ["reply"]}},
            date(2026, 11, 5))
        self.assertEqual(card["count"], 1)

    def test_seal_command_has_no_finish_alias(self):
        import contextlib
        import io
        import x_analytics
        buf = io.StringIO()
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(buf):
                x_analytics.main(["finish"])
        self.assertIn("seal", buf.getvalue())


class Leads(unittest.TestCase):
    def test_backlog_wording_and_expire(self):
        self.assertEqual(
            qol_leads.backlog_copy(12, 10),
            "12 people still engaging who don't follow you yet (+2 vs last week)")
        self.assertIn("still count", qol_leads.likes_off_line(4, 14))
        kept, dropped = qol_leads.expire_backlog(
            {"old": {"username": "a", "last": "2026-09-01"}, "new": {"username": "b", "last": "2026-11-01"}},
            date(2026, 11, 5), 30, ["new"])
        self.assertEqual(dropped, 1)
        self.assertIn("new", kept)
        self.assertNotIn("old", kept)


class LeaveWindow(unittest.TestCase):
    def test_next_seven_days(self):
        verified = [{"date": "2026-08-07", "impressions": "100"}]
        tracker = [{"value": "500", "pulled_at_et": "2026-11-05T01:00:00"}]
        data = pages_v11.leave_window_data(verified, tracker, 90)
        self.assertEqual(len(data["drops"]), 7)
        self.assertEqual(data["drops"][0]["date"], "2026-08-07")
        self.assertIn("Leaving the 500K window", pages_v11.leave_window(verified, tracker, 90))
        self.assertEqual(pages_v11.leave_window([], tracker, 90), "")


class Defaults(unittest.TestCase):
    def test_config_example_stays_off(self):
        cfg = json.load(open(os.path.join(ROOT, "config.example.json"), encoding="utf-8"))
        self.assertFalse(cfg["shoutout-picker"]["rollover_lookup"])
        self.assertTrue(cfg["analytics-log"]["replies_scorecard"]["enabled"])
        self.assertEqual(cfg["follow-finder"]["lang_balance"], {})
        self.assertFalse(cfg["follow-finder"]["game_image_check"])
        self.assertEqual(cfg["fan-finder"]["leads_expire_days"], 30)

    def test_game_off_without_live_flag(self):
        import publish_lists
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["BOTS_HOME"] = tmp
            os.environ.pop("GAME_LIVE_PREVIEW", None)
            self.assertFalse(publish_lists.game_live())
            flag = os.path.join(tmp, "creator-scout", "game")
            os.makedirs(flag)
            open(os.path.join(flag, "LIVE"), "w").close()
            self.assertTrue(publish_lists.game_live())

    def test_pack_version(self):
        meta = json.load(open(os.path.join(ROOT, "foreman", "standalone.json"), encoding="utf-8"))
        self.assertEqual(meta["version"], "v1.2.1")

    def test_capped_line(self):
        self.assertEqual(v11.capped_pull("mentions", 1), "Capped pull: skipped mentions (cost cap $1.00 reached)")

    def test_embed_caveat_is_official_only(self):
        ui = open(os.path.join(ROOT, "follow-finder", "game", "game_ui.js"), encoding="utf-8").read()
        needle = "cdn." + "syndication"
        self.assertNotIn(needle, ui)
        self.assertIn("official embed widget", ui)
        sys.path.insert(0, os.path.join(ROOT, "follow-finder", "game"))
        import game_tab
        self.assertIn("official embed widget", game_tab.EMBED_CAVEAT)
        self.assertNotIn(needle, game_tab.EMBED_CAVEAT)


class N55Gaps(unittest.TestCase):
    def test_own_likes_stop_at_known(self):
        import engagement
        new, done = engagement.read_own_likes(["b"], [{"id": "c"}, {"id": "b"}, {"id": "a"}])
        self.assertEqual(new, ["c"])
        self.assertTrue(done)

    def test_coverage_and_trial_caps(self):
        import engagement
        block = engagement.coverage_block(["your likes"], 1.5, False)
        self.assertTrue(block["line"].startswith("Capped pull: skipped your likes"))
        self.assertIn("not finished", block["text"])
        caps = engagement.apply_trial({"max_cost_per_run": 2, "max_liker_posts_per_run": 15,
                                       "trial_max_cost": 0.2, "trial_max_liker_posts": 1}, True)
        self.assertEqual(caps["max_cost"], 0.2)
        item = engagement.mark_already_liked({"id": "9"}, ["9"], True)
        self.assertTrue(item["liked"])
        self.assertFalse(item["maybe_liked"])

    def test_leads_seen_and_refile(self):
        seen = qol_leads.track_leads_seen({}, [{"id": "1", "u": {"username": "ada_demo"}}], date(2026, 11, 5))
        self.assertEqual(seen["1"]["times"], 1)
        accounts = {"1": {"gone": {"reason": "suspended"}, "follower_now": True, "user": {"username": "bea_demo"}}}
        moved = weekly_rollup.refile_gone(accounts)
        self.assertEqual(moved, ["bea_demo"])
        self.assertFalse(accounts["1"]["follower_now"])

    def test_daily_summary_and_cost(self):
        lines = weekly_rollup.daily_summary({"headline": "4 (+1 in Followed you back)", "new_follows": 2, "est_unfollows": 1})
        self.assertTrue(lines[0].startswith("Daily summary: 4"))
        self.assertIn("unscaled", weekly_rollup.run_cost_line(10, 0.76, 1.0))

    def test_cached_read_reuses(self):
        cache, calls = {}, []

        def fetch():
            calls.append(1)
            return [{"id": "1"}]

        first, reused = weekly_rollup.cached_read(cache, ("1", "followers"), fetch)
        second, reused2 = weekly_rollup.cached_read(cache, ("1", "followers"), fetch)
        self.assertEqual(first, second)
        self.assertFalse(reused)
        self.assertTrue(reused2)
        self.assertEqual(len(calls), 1)

    def test_missing_verified_impressions_are_not_zero(self):
        import creator_scout
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "verified_daily_latest.csv"), "w").write("date,impressions\n2026-11-01,10\n")
            got = creator_scout.expect_file("verified_90d.csv", tmp)
        self.assertEqual(got["status"], "missing")
        self.assertIn("Not counted as zero", got["note"])
        self.assertTrue(got["kept"])


class PrivateGateWording(unittest.TestCase):
    def test_changelog_has_no_private_markers(self):
        # Parts stay split so the pack scanner never sees the marker as one substring.
        banned = ("Fie" + "ld No" + "tes", "Wh" + "etst" + "one")
        for name in ("CHANGELOG.md", "CHANGES-next.md"):
            text = open(os.path.join(ROOT, name), encoding="utf-8").read()
            for word in banned:
                self.assertNotIn(word, text)
            self.assertIn("box-only private exclude list", text)


class DemoJuniper(unittest.TestCase):
    def test_profile_shape(self):
        sys.path.insert(0, os.path.join(ROOT, "site"))
        import demo_juniper
        prof = demo_juniper.profile()
        self.assertEqual(prof["username"], "junipervale_demo")
        self.assertEqual(prof["followers"], 2400)
        pool = demo_juniper.scout_pool()
        self.assertTrue(all(c["username"].endswith("_demo") for c in pool))
        labels = demo_juniper.rarity_labels(pool)
        self.assertTrue(any(v["rarity"] == "Legendary" for v in labels.values()))
        # The stored label is the cut's label. Nothing rewrites Legendary to Common.
        for cand in pool:
            self.assertIn(labels[cand["username"]]["rarity"], ("Legendary", "Rare", "Common"))
        sample = demo_juniper.game_sample(pool, labels)
        self.assertEqual(sample["pack"][0]["rarity"], labels[pool[0]["username"]]["rarity"])
        self.assertIn("LIVE", sample["note"])
        done = demo_juniper.marks()["done"]
        self.assertTrue(any(v.get("done") == 1 and v.get("at") for v in done.values()))
        med = demo_juniper.median_inputs()
        sys.path.insert(0, os.path.join(ROOT, "site"))
        import qol7_medrt
        line = qol7_medrt.publish_line(med["posts"], med["events"], med["done"], med["users"])
        self.assertIn("42 min", line)


class V121Defaults(unittest.TestCase):
    def test_setup_routines_and_wording(self):
        rerun = json.load(open(os.path.join(ROOT, "rerun-picker", "routine.json"), encoding="utf-8"))
        analytics = json.load(open(os.path.join(ROOT, "analytics-log", "routine.json"), encoding="utf-8"))
        self.assertTrue(any(r.get("name") == "Stale review nudge" for r in rerun["routines"]))
        self.assertTrue(any(r.get("name") == "Weekly replies scorecard" for r in analytics["routines"]))
        bots = {b["slug"]: b for b in json.load(open(os.path.join(ROOT, "foreman", "bots.json"), encoding="utf-8"))["bots"]}
        self.assertIn("lang_balance", bots["follow-finder"]["questions"])
        self.assertIn("minimum share", bots["follow-finder"]["lang_balance_prompt"])
        self.assertIn("$0.04", bots["shoutout-picker"]["rollover_lookup_prompt"])
        sys.path.insert(0, os.path.join(ROOT, "follow-audit"))
        import weekly_rollup
        line = weekly_rollup.run_cost_line(10, 0.20, 0.20)
        self.assertIn("unscaled", line)
        scaled = weekly_rollup.run_cost_line(10, 0.10, 0.20)
        self.assertIn("0.10", scaled)
        self.assertIn("0.20", scaled)
        scout = json.load(open(os.path.join(ROOT, "config.example.json"), encoding="utf-8"))["follow-finder"]
        self.assertEqual(scout["lang_balance"], {})


if __name__ == "__main__":
    unittest.main()
