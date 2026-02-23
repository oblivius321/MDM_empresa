import urllib.request
import json
import sys

BASE_URL = "http://127.0.0.1:8000/api"

def enroll_device():
    print("--- Tentando cadastrar dispositivo ---")
    url = f"{BASE_URL}/enroll"
    data = {
        "device_id": "teste_user_01",
        "name": "Notebook do Usuario",
        "device_type": "windows",
        "is_active": True,
        # New frontend fields
        "imei": "1234567890123456",
        "model": "ThinkPad X1",
        "company": "Minha Empresa"
    }
    
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                result = json.loads(response.read().decode('utf-8'))
                print("✅ SUCESSO! Dispositivo cadastrado:")
                print(json.dumps(result, indent=2))
            else:
                print(f"❌ Erro: Status {response.status}")
                
    except urllib.error.HTTPError as e:
        print(f"❌ Erro HTTP {e.code}: {e.read().decode()}")
    except urllib.error.URLError as e:
        print(f"❌ Falha na conexão: {e}")
        print("DICA: Verifique se o backend está rodando.")

def list_devices():
    print("\n--- Listando dispositivos no banco ---")
    url = f"{BASE_URL}/devices"
    try:
        with urllib.request.urlopen(url) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"Encontrados {len(result)} dispositivos:")
            print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Erro ao listar: {e}")

if __name__ == "__main__":
    enroll_device()
    list_devices()
