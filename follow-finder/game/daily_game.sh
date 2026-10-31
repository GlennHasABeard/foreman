#!/bin/bash
# Follow Finder daily Game build. Run AFTER creator_scout.py and the vision step, so every pack
# is built from vision-checked picks. $0: no X API calls (build prints "X calls: 0").
# Order for Follow Finder's routine:
#   1. CREW_BOT="Follow Finder" python3 $BOTS_HOME/creator-scout/creator_scout.py run
#   2. OPTIONAL image check, only if game_image_check is true (off by default, costs X credits, shown first):
#      python3 $BOTS_HOME/creator-scout/game/nsfw/daily_vision.py cost ; ... prep --yes   (bot views sheets/daily_*.jpg)
#      python3 $BOTS_HOME/creator-scout/game/nsfw/daily_vision.py rate HANDLE safe|suggestive|explicit|unchecked "note"
#      python3 $BOTS_HOME/creator-scout/game/nsfw/daily_vision.py apply
#   3. bash $BOTS_HOME/creator-scout/game/daily_game.sh                  (this script)
#   4. CREW_BOT="Follow Finder" python3 $BOTS_HOME/site/publish_lists.py (ships game.json only if game/LIVE exists)
# CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID come from stored secrets (hosted only). Without them the build
# still runs and keeps marks in the local store.
set -e
BOTS_HOME="${BOTS_HOME:-/workspace}"
G="$BOTS_HOME/creator-scout/game"
cd "$G"
mkdir -p nsfw/sheets nsfw/img live
P=$(python3 -c "import sys,os,json;sys.path.insert(0,'nsfw');sys.path.insert(0,'.');import game_tab as g;V=g.rj('nsfw/vision.json',{});print(sum(1 for c in g.scout_picks() if c['username'].lower() not in V))")
[ "$P" = "0" ] || echo "WARNING: $P of today's picks have no vision verdict, they stay blurred behind Tap to show."
GAME_STORE="$G/store.json" python3 game_tab.py build --out "$G/live"
