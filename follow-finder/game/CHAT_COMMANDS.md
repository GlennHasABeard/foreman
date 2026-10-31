# Follow Finder Game: chat commands

When the owner says any of these in chat, run the matching command. $0, no X calls.

- "not like @handle because <reason>"
  `cd $BOTS_HOME/creator-scout/game && python3 game_tab.py chat "not like @handle because <reason>"`
- "undo rule <id, chip name, or words from the rule>"
  `cd $BOTS_HOME/creator-scout/game && python3 game_tab.py chat "undo rule <text>"`
- "already following @handle"
  `cd $BOTS_HOME/creator-scout/game && python3 game_tab.py chat "already following @handle"` (same as the page's Already following button; keeps them out until Follow Audit's list catches up)

Hosted: CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID come from stored secrets (never print them). The command writes the local store (game/store.json) and, when hosted, the KV page `checks:game-rules` (or `checks:game-following`), the same place the page's Rules learned writes, so phone, desktop and chat stay in sync. Not hosted, it saves locally only.
Reasons that name a chip (engagement bait, follow trains or giveaways, not my niche, too big already, politics or rage posts, nsfw, mostly self promo, reposts other people's work, low effort or spammy ai) become that chip's rule. Anything else becomes a "your words" rule.
Reply with the command's one-line output. If it says "More than one rule matches", list those and ask which one. Rules apply from the next pack.
