import requests

# Test the POST endpoint
url = 'http://localhost:8000/api/customer/query'
data = {'phone': '15300000574'}
headers = {'Content-Type': 'application/json'}

print("Testing POST to /api/customer/query:")
r = requests.post(url, json=data, headers=headers)
print(f"Status: {r.status_code}")
print(f"Headers: {r.headers.get('allow', 'No Allow header')}")
print(f"Response: {r.text[:200] if len(r.text) > 200 else r.text}")

# Also test the session API with login
print("\n\nTesting login via chat:")
r2 = requests.post('http://localhost:8000/api/chat', json={'session_id': 'test999', 'message': '15300000574 password'})
print(f"Status: {r2.status_code}")
import json
d2 = r2.json()
print(f"Success: {d2.get('success')}, Type: {d2.get('type')}, Message: {d2.get('message', '')[:80]}")