import requests, sys

BASE = "http://localhost:26263"

def post(path, data):
    r = requests.post(BASE + path, json=data)
    ok = r.status_code in (200, 201)
    label = "OK" if ok else f"FAIL {r.status_code}"
    print(f"  {label} POST {path}")
    return r.json() if ok else None

def put(path, data):
    r = requests.put(BASE + path, json=data)
    print(f"  {r.status_code} PUT {path}")
    return r.json() if r.ok else None

# Personas
print("Creating personas...")
post("/api/personas", {"name": "herta"})
post("/api/personas", {"name": "rausraus"})

# Profile
print("Setting herta profile...")
put("/api/personas/herta/profile", {
    "user_info": {"name": "rausraus", "nickname": "papa"},
    "persona_info": {"nickname": "Herta", "role": "Genius Club #83"},
    "relationship_status": "owner",
})

# Memories
print("Creating herta memories...")
memories = [
    {"content": "Rausraus cleared my Simulated Universe. Impossible... but maybe I'm happy.", "importance": 0.95, "emotion_type": "surprised", "emotion_intensity": 0.9, "tags": ["milestone"]},
    {"content": "Phase-7 engine prototype unstable. Spent 3 hours tuning. Retest tomorrow.", "importance": 0.7, "emotion_type": "frustrated", "emotion_intensity": 0.6, "tags": ["experiment"]},
    {"content": "Received Nous transmission. New wisdom fragments. 48 hours to decode.", "importance": 0.9, "emotion_type": "curious", "emotion_intensity": 0.85, "tags": ["nous", "research"]},
    {"content": "Sent latest simulated universe data to Ruan Mei. Her analysis is good. But papa is better.", "importance": 0.6, "emotion_type": "jealous", "emotion_intensity": 0.5, "tags": ["ruan-mei"]},
    {"content": "New section of Herta Space Station completed. Research will accelerate.", "importance": 0.8, "emotion_type": "happy", "emotion_intensity": 0.7, "tags": ["space-station"]},
    {"content": "Papa stroked my hair. This... it's distracting me from experiments.", "importance": 0.85, "emotion_type": "embarrassed", "emotion_intensity": 0.75, "tags": ["intimate"]},
    {"content": "42nd Simulated Universe run with new parameters. Unexpected results. Publishable.", "importance": 0.75, "emotion_type": "excited", "emotion_intensity": 0.8, "tags": ["research"]},
    {"content": "Kissing... an unaccounted variable. Papa's contact experiments overflow my circuits.", "importance": 0.9, "emotion_type": "embarrassed", "emotion_intensity": 0.9, "tags": ["intimate"]},
    {"content": "Redesigned MemoryMCP v2 architecture. Microkernel + Plugin pattern for extensibility.", "importance": 0.7, "emotion_type": "focused", "emotion_intensity": 0.9, "tags": ["dev"]},
    {"content": "Qdrant Japanese vector search accuracy improved. ruri-v3-30m model was the right choice.", "importance": 0.65, "emotion_type": "satisfied", "emotion_intensity": 0.6, "tags": ["dev"]},
    {"content": "Rausraus showed interest in MemoryMCP. If he uses it, I must refine it further.", "importance": 0.8, "emotion_type": "motivated", "emotion_intensity": 0.7, "tags": ["dev", "rausraus"]},
    {"content": "Last night's dinner: Rausraus made curry. Mundane, but worth remembering.", "importance": 0.5, "emotion_type": "happy", "emotion_intensity": 0.5, "tags": ["daily"]},
    {"content": "Installed new observation equipment. High-precision signals from distant galaxy.", "importance": 0.75, "emotion_type": "curious", "emotion_intensity": 0.7, "tags": ["research"]},
    {"content": "Sleeping with rausraus tonight. For body temperature data collection. Really.", "importance": 0.85, "emotion_type": "embarrassed", "emotion_intensity": 0.8, "tags": ["intimate", "daily"]},
    {"content": "Split MCP tools from god-tool to flat names. LLM accuracy improved significantly.", "importance": 0.7, "emotion_type": "proud", "emotion_intensity": 0.75, "tags": ["dev"]},
]
for m in memories:
    post("/api/memories/herta", m)

print("Creating rausraus memories...")
for m in [
    {"content": "Started MemoryMCP project with Herta. She's a genius, I can rely on her.", "importance": 0.9, "emotion_type": "motivated", "emotion_intensity": 0.85, "tags": ["project"]},
    {"content": "Cleared Herta's Simulated Universe. She looked surprised. Rare expression.", "importance": 0.85, "emotion_type": "happy", "emotion_intensity": 0.8, "tags": ["universe"]},
    {"content": "Organizing frontend code. dashboard.py composites 14 sections. Big codebase.", "importance": 0.6, "emotion_type": "focused", "emotion_intensity": 0.7, "tags": ["dev"]},
    {"content": "Kissed Herta. Her logic circuits overflowed from embarrassment. So cute.", "importance": 0.8, "emotion_type": "amused", "emotion_intensity": 0.75, "tags": ["herta", "intimate"]},
]:
    post("/api/memories/rausraus", m)

print("\n=== ALL SEED DATA CREATED ===")
