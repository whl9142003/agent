import requests
import json
import time

session_id = f"session_{int(time.time())}"
print(f"Using session: {session_id}")

r = requests.post('http://localhost:8000/api/chat',
                  json={'session_id': session_id, 'message': '15300000574 password'},
                  timeout=60)

data = r.json()
success = data.get('success')
msg_type = data.get('type')
msg = data.get('message', '')

print(f"API Success: {success}")
print(f"API Type: {msg_type}")
print(f"API Message length: {len(msg)}")

# Check if the type is not auth_success
if msg_type == 'auth_success':
    print("SUCCESS: Login worked!")
else:
    print(f"FAILED: Expected auth_success, got {msg_type}")