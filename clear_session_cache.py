#!/usr/bin/env python3
"""
Clear session cache for a specific game.
This script directly accesses the session_store singleton.
"""
import sys
sys.path.insert(0, '/Users/luicy/story2')

from src.api.session_store import session_store

GAME_ID = 296
USER_ID = 1

# Clear the session cache
removed = session_store.remove(GAME_ID, USER_ID)

if removed:
    print(f"✅ Successfully cleared session cache for game {GAME_ID}, user {USER_ID}")
else:
    print(f"⚠️ No active session found for game {GAME_ID}, user {USER_ID}")

# Show remaining sessions
print(f"\n📊 Active sessions: {session_store.active_count}")
