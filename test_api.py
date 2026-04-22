import requests
import json
import time

# Use a unique session ID each time
session_id = f"session_{int(time.time())}"

print(f"Testing with session_id: {session_id}")

# Test login
r = requests.post('http://localhost:8000/api/chat', 
                  json={'session_id': session_id, 'message': '15300000574 password'},
                  timeout=60)
                  
print(f"Status: {r.status_code}")
data = r.json()
print(f"Success: {data.get('success')}")
print(f"Type: {data.get('type')}")
print(f"Message: {data.get('message', '')}")
print(f"Full response: {json.dumps(data, ensure_ascii=False)}")