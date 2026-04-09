try:
    from backend.api import policy_routes
    print("policy_routes imported successfully")
except Exception as e:
    print(f"Failed to import policy_routes: {e}")
    import traceback
    traceback.print_exc()
