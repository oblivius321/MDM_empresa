import json
import urllib.request
import urllib.error

url = "http://localhost:3000/api/auth/login"

payload = {
    "email": "admin@empresa.com",
    "password": "AdminSenhaForte123!"
}

print(f"Enviando POST para {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print()

try:
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        method='POST',
        headers={'Content-Type': 'application/json'}
    )
    
    with urllib.request.urlopen(req, timeout=10) as response:
        print(f"Status Code: {response.status}")
        print(f"Headers: {dict(response.headers)}")
        body = response.read().decode('utf-8')
        print(f"Body: {body}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}")
    print(f"Body: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Erro: {e}")
