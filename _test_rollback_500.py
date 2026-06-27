"""Quick test: rollback non-existent session."""

import json
import urllib.request

# Rollback non-existent session
data = json.dumps({"keep_until": 0}).encode()
req = urllib.request.Request(
    "http://localhost:26262/api/chat/herta/sessions/NO_SUCH_SESSION/rollback",
    data=data,
    headers={"Content-Type": "application/json", "X-Persona": "herta"},
    method="POST",
)
try:
    r = urllib.request.urlopen(req, timeout=10)
    print(f"STATUS: {r.status}")
    print(f"BODY: {r.read().decode()}")
except urllib.error.HTTPError as e:
    print(f"STATUS: {e.code}")
    print(f"BODY: {e.read().decode()}")
except Exception as e:
    print(f"ERROR: {e}")
