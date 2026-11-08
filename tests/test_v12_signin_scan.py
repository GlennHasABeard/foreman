"""Block setup instructions that tell a bot to collect a callback or secret in chat.

The scanner reads public instruction files. A bad example and a protective example
live in this test, not in a shipped guide.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A negation covers the words that follow it until a period or semicolon.
# "or" lists stay inside that cover, so "never the code, or a token in chat" stays covered.
# Only a prohibition of an ask/paste/copy/send verb is removed. "does not load"
# is not a prohibition, so the words after it stay visible to the scan.
NEGATED = re.compile(
    r"\b(?:do not|don't|does not|doesn't|never|no longer)\s+"
    r"(?:ask|paste|copy|put|send|give|hand|use|tell|pass|share)\b"
    r"(?:[^.\n;]|\bor\b[^.\n;])*",
    re.I,
)
UNSAFE = [
    re.compile(r"paste it here", re.I),
    re.compile(r"paste it right away", re.I),
    re.compile(r"paste faster", re.I),
    re.compile(r"paste backup", re.I),
    re.compile(r"pastes it to", re.I),
    re.compile(r"paste (?:it|the address|the full address|the callback|them) (?:to|into|in)\b", re.I),
    re.compile(r"copy the full address", re.I),
    re.compile(r"copy the address bar", re.I),
    re.compile(r"auth-paste\s+['\"<]", re.I),
    re.compile(r"\bauth\s+--paste\b", re.I),
    re.compile(
        r"\b(?:send|give|put|share)\b[^.\n]{0,80}\b(?:callback|authorization code|the code|the token|client secret)\b[^.\n]{0,40}\b(?:chat|here)\b",
        re.I,
    ),
]
# Markdown can name the old command by itself. A script may still list that
# command without telling anyone to pass a callback into it.
UNSAFE_MARKDOWN = UNSAFE + [re.compile(r"\bauth-paste\b", re.I)]


def exposed(text):
    """Instruction text with negated clauses removed."""
    return NEGATED.sub(" ", text)


def unsafe_hits(text, patterns=None):
    """Return matched unsafe phrases that are not inside a prohibition."""
    visible = exposed(text)
    hits = []
    for pattern in patterns or UNSAFE_MARKDOWN:
        found = pattern.search(visible)
        if found:
            hits.append(found.group(0))
    return hits


def instruction_files(root=ROOT):
    """Shipped instruction text, including script messages. Tests are fixtures, not setup."""
    found = []
    skip_dirs = {".git", "__pycache__", "tests"}
    exts = {".py", ".md", ".txt", ".sh", ".js", ".json", ".html"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for name in filenames:
            if os.path.splitext(name)[1] in exts:
                found.append(os.path.join(dirpath, name))
    return found


class SignInInstructionScan(unittest.TestCase):
    def test_public_instructions_have_no_chat_callback_fallback(self):
        bad = []
        for path in instruction_files():
            text = open(path, encoding="utf-8").read()
            patterns = UNSAFE if path.endswith(".py") else UNSAFE_MARKDOWN
            hits = unsafe_hits(text, patterns)
            if hits:
                bad.append(os.path.relpath(path, ROOT) + ": " + ", ".join(hits))
        self.assertEqual(bad, [])

    def test_bad_fixture_is_blocked_including_wrapped_phrasing(self):
        samples = [
            "If the page does not load, copy the full address from the address bar and paste it here.",
            "When they paste it, run auth-paste '<address>'.",
            "Ask the owner to send the callback URL in chat.",
            "Put the token in chat so sign-in can finish.",
            "The backup, which you should use if the page fails, is to copy the full address from the address bar and paste it here right away.",
            "Use auth --paste and give Foreman the address.",
            "Backup, only if the page after Authorize doesn't load: copy the full address from the address bar and paste it right away.",
            "Can't listen. Use the paste backup.",
            "Run auth again and approve in the bot's browser, or paste faster.",
            "the owner copies the full address from the address bar and pastes it to Foreman",
            "python3 follow_watch.py auth-paste '<address>'",
        ]
        for sample in samples:
            self.assertTrue(unsafe_hits(sample), sample)

    def test_protective_wording_is_allowed(self):
        samples = [
            "Never ask for the callback address, the code, or a token in chat.",
            "Do not paste the client secret in chat.",
            "Do not put a callback address, code, or token into a command, a log, or this chat.",
            "They no longer tell the bot to pass that address to auth-paste.",
            "Callback URI / Redirect URL: enter exactly http://127.0.0.1:8765/callback",
            "If the script prints a backup that asks for that address, do not use it.",
            "Secrets only in stored secrets. Never in chat.",
            "Older guides could ask you to paste a sign-in callback into chat if automatic sign-in failed. If you did that, disconnect and reconnect this app in your own X Connected apps settings, then run setup again. No action is needed if sign-in worked automatically.",
            'help="local stdin only. Do not take a callback address from chat."',
        ]
        for sample in samples:
            self.assertEqual(unsafe_hits(sample, UNSAFE), [], sample)
            self.assertEqual(unsafe_hits(sample), [], sample)
        command_name = 'choices=["auth", "auth-paste", "signin-check"]'
        self.assertEqual(unsafe_hits(command_name, UNSAFE), [])

    def test_analytics_guide_has_no_callback_fallback(self):
        text = open(os.path.join(ROOT, "guides", "analytics-log.md"), encoding="utf-8").read()
        self.assertNotIn("auth-paste", text)
        self.assertNotIn("paste it here", text)
        self.assertEqual(unsafe_hits(text), [])


if __name__ == "__main__":
    unittest.main()
