#!/usr/bin/env python3
"""Check if test_echo skill appears in chat debug prompt."""
import asyncio
import json

import aiohttp


async def check():
    async with aiohttp.ClientSession() as s, s.post(
        "http://localhost:26262/api/chat/herta",
        json={"message": "hi", "session_id": "debug_skill_check", "debug": True}
    ) as resp:
        async for line in resp.content:
            line = line.decode().strip()
            if line.startswith('data:') and 'system_prompt' in line:
                data = json.loads(line[5:])
                sp = data.get("system_prompt", "")
                if "test_echo" in sp:
                    print("✅ test_echo skill FOUND in system prompt!")
                    for sline in sp.split("\n"):
                        if "test_echo" in sline or "利用可能なSkill" in sline:
                            print(f"  {sline}")
                else:
                    print("❌ test_echo skill NOT found in system prompt")
                    # Show skill section area
                    lines = sp.split("\n")
                    for i, sline in enumerate(lines):
                        if "Skill" in sline or "skill" in sline.lower():
                            print(f"  [{i}] {sline}")
                break
    await s.close()

asyncio.run(check())
