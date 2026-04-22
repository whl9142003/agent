import requests
import json
import time

session_id = f"session_{int(time.time())}"
print(f"Using session: {session_id}")

# First test the customer query API directly
r = requests.get('http://localhost:8000/api/customer/120000', timeout=30)
print(f"Customer query status: {r.status_code}")
print(f"Customer query response: {r.text[:200] if len(r.text) > 200 else r.text}")

# Now test the chat
r2 = requests.post('http://localhost:8000/api/chat',
                  json={'session_id': session_id, 'message': '15300000574 password'},
                  timeout=60)

data = r2.json()
print(f"\nChat Success: {data.get('success')}")
print(f"Chat Type: {data.get('type')}")
print(f"Chat Message length: {len(data.get('message', ''))}")