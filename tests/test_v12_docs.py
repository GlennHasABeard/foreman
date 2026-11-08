"""v1.2.2 docs contract. The guides are the setup a stranger follows. No share is claimed."""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GUIDES = [
    "guides/follow-audit.md",
    "guides/follow-finder.md",
    "guides/shoutout-picker.md",
    "guides/reply-queue.md",
    "guides/fan-finder.md",
    "guides/rerun-picker.md",
    "guides/analytics-log.md",
]

RULES = [
    "Stay out of X Chat.",
    "Book every request in the ledger before the next.",
    "If the cap stops a run, say what was not read.",
    "Never ask for, print or write a key, token or password",
    "Never report a fake 0 or empty list for something not read.",
    "Never overwrite raw files or pulls",
    "No memory, routines or secrets until setup is finished.",
    "ask before replacing it",
    "update_check.py check",
    "update_check.py fetch <tag> --yes",
    "only after the owner says yes to that routine",
    "Never create a routine they did not accept",
]

SILENT = (
    "Setup installs",
    "installed at setup",
    "Do not wait for the owner",
)


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


class V122Docs(unittest.TestCase):
    def test_pack_pin_uses_sums_file_not_a_self_hash(self):
        meta = json.loads(read("foreman/standalone.json"))
        self.assertEqual(meta["version"], "v1.2.3")
        fetch = read("foreman/fetch_release.sh")
        self.assertIn('TAG="${1:-v1.2.3}"', fetch)
        self.assertIn("sha256sum -c", fetch)
        # The published v1.2.1 digest stays on that release. It is not this zip's digest.
        for rel in ("README.md", "INSTALL_MESSAGE.txt", "foreman/instructions.md", "foreman/fetch_release.sh"):
            text = read(rel)
            self.assertNotIn("496973edd90168e48cba4798233dad7af0b3bb9513239e1188352ff290b352d7", text)
            self.assertIn("SHA256SUMS", text)
            self.assertIn("v1.2.3", text)
        readme = read("README.md")
        self.assertIn("does not claim those shares are accepted", readme)
        self.assertIn("stranger install", readme.lower())

    def test_seven_guides_carry_full_profile_rules(self):
        for rel in GUIDES:
            text = read(rel)
            for phrase in RULES:
                self.assertIn(phrase, text, rel)
            for phrase in SILENT:
                self.assertNotIn(phrase, text, rel)
            self.assertIn("/workspace/foreman/foreman/fetch_release.sh v1.2.3 --bot ", text)
            self.assertNotIn("v1.2.1", text, rel)
        # Analytics has no X sign-in. The other six keep reuse and force consent.
        for rel in GUIDES:
            if rel.endswith("analytics-log.md"):
                self.assertIn("no x api", read(rel).lower())
                continue
            text = read(rel)
            self.assertIn("signin-check", text)
            self.assertIn("auth --force", text)
            self.assertIn("Reusing", text)
            self.assertIn("Never ask for the callback address, the code, or a token in chat.", text)
            self.assertIn("do not put a callback address, code, or token into a command", text)

    def test_named_routines_match_routine_json(self):
        pairs = {
            "guides/follow-audit.md": "follow-audit/routine.json",
            "guides/follow-finder.md": "follow-finder/routine.json",
            "guides/shoutout-picker.md": "shoutout-picker/routine.json",
            "guides/reply-queue.md": "reply-queue/routine.json",
            "guides/fan-finder.md": "fan-finder/routine.json",
            "guides/rerun-picker.md": "rerun-picker/routine.json",
            "guides/analytics-log.md": "analytics-log/routine.json",
        }
        for guide, routine in pairs.items():
            body = read(guide)
            start = body.index("## Routines")
            end = body.index("## Introduce yourself")
            section = body[start:end]
            for item in json.loads(read(routine))["routines"]:
                self.assertIn(item["name"], section, guide)
        foreman = read("foreman/instructions.md")
        for name in ("Daily spend line", "Update check"):
            self.assertIn(name.lower() if name == "Daily spend line" else name, foreman if name != "Daily spend line" else foreman.lower())
        self.assertIn("daily spend line", foreman.lower())
        nudge = json.loads(read("rerun-picker/routine.json"))
        prompt = next(r["prompt"] for r in nudge["routines"] if r["name"] == "Stale review nudge")
        self.assertNotIn("Do not wait", prompt)
        self.assertIn("owner said yes", prompt)

    def test_old_profile_specifics_still_present(self):
        self.assertIn("$0.65 to $1.00", read("guides/follow-audit.md"))
        self.assertIn("turn on Game", read("guides/follow-finder.md"))
        self.assertIn("Never scan without a yes.", read("guides/shoutout-picker.md"))
        self.assertIn("may already be liked", read("guides/reply-queue.md"))
        self.assertIn("$0.25 to $1.07", read("guides/fan-finder.md"))
        self.assertIn("$0.001 per post", read("guides/rerun-picker.md"))
        self.assertIn("Never ask for their password", read("guides/analytics-log.md"))
        self.assertIn("finished", read("guides/analytics-log.md"))

    def test_foreman_installs_full_file_set_and_handoff(self):
        text = read("foreman/instructions.md")
        for phrase in (
            "standalone.json",
            "v11_wire.py",
            "dispatch/instructions.md",
            "dispatch/routine.json",
            "dispatch/selfcheck.py",
            "dispatch/spend.py",
            "follow_watch.py",
            "x_prices.py",
            "bot_spend.py",
            "CHAT_COMMANDS.md",
            "daily_game.sh",
            "game_tab.py",
            "game_ui.js",
            "daily_vision.py",
            "nsfw.py",
            "refilter_today.py",
            "not like @name because",
            "undo rule",
            "already following @name",
            "shoutout goal N",
            "raise the cap to $X for today",
            "repeat the amount and the date",
            "v11.py chat",
            "update_check.py check",
            "update_check.py fetch <tag> --yes",
            "stay out of X Chat",
            "edit lists",
            "0 that isn't real",
            "ledger before the next",
            "ask before replacing it",
            "costcheck.py",
            "Never ask for the callback address, the code, or a token in chat.",
            "auth --force",
        ):
            self.assertIn(phrase, text)
        for phrase in SILENT:
            self.assertNotIn(phrase, text)

    def test_commands_name_files_that_exist(self):
        files = set()
        for rel in GUIDES + ["foreman/instructions.md", "INSTALL_MESSAGE.txt", "README.md"]:
            text = read(rel)
            for match in re.findall(r"/workspace/foreman/([A-Za-z0-9_./-]+\.(?:py|sh|md|json))", text):
                if match.endswith("plan.json"):
                    continue
                files.add(match)
        missing = [rel for rel in sorted(files) if not os.path.isfile(os.path.join(ROOT, rel))]
        self.assertEqual(missing, [])
        meta = json.loads(read("foreman/standalone.json"))
        listed = []
        for bot in meta["bots"]:
            listed.extend(bot["files"])
        absent = [rel for rel in sorted(set(listed)) if not os.path.isfile(os.path.join(ROOT, rel))]
        self.assertEqual(absent, [])

    def test_changelog_does_not_claim_share_acceptance(self):
        log = read("CHANGELOG.md")
        self.assertIn("## v1.2.3", log)
        self.assertIn("## v1.2.2", log)
        self.assertIn("does not say share acceptance is done", log)
        self.assertNotIn("stranger install passed", log.lower())
        notes = read("PATCH-NOTES.md")
        self.assertIn("does not say a share was accepted", notes)


if __name__ == "__main__":
    unittest.main()
