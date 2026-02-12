import json
from datetime import datetime
from typing import List, Dict

class Device:
    def __init__(self, device_id: str, name: str, device_type: str):
        self.device_id = device_id
        self.name = name
        self.device_type = device_type
        self.enrollment_date = datetime.now()
        self.is_active = True
        self.policies = []

class MDMSystem:
    def __init__(self):
        self.devices: Dict[str, Device] = {}
        self.policies: List[Dict] = []

    def enroll_device(self, device_id: str, name: str, device_type: str) -> Device:
        device = Device(device_id, name, device_type)
        self.devices[device_id] = device
        return device

    def remove_device(self, device_id: str) -> bool:
        if device_id in self.devices:
            del self.devices[device_id]
            return True
        return False

    def apply_policy(self, device_id: str, policy: Dict) -> bool:
        if device_id in self.devices:
            self.devices[device_id].policies.append(policy)
            return True
        return False

    def list_devices(self) -> List[Device]:
        return list(self.devices.values())

    def get_device(self, device_id: str) -> Device:
        return self.devices.get(device_id)


if __name__ == "__main__":
    mdm = MDMSystem()
    
    # Exemplo de uso
    device = mdm.enroll_device("DEV001", "iPhone 12", "iOS")
    print(f"Device enrolled: {device.name}")
    
    policy = {"security": "enabled", "lock_screen": True}
    mdm.apply_policy("DEV001", policy)
    
    for dev in mdm.list_devices():
        print(f"{dev.name} - {dev.device_type}")