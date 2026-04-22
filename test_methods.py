import requests

methods = ['GET', 'POST', 'PUT', 'DELETE']
for method in methods:
    r = requests.request(method, 'http://localhost:8000/api/customer/query', timeout=5)
    print(f'{method}: {r.status_code} - {r.text[:50]}')