import sys
import os
sys.path.append(os.getcwd())

try:
    from backend.main import app
    print("Routes loaded:")
    for route in app.routes:
        if hasattr(route, 'path'):
            print(f"{route.path}")
except Exception as e:
    print(f"Error: {e}")
