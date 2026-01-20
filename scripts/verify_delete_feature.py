import requests
import time

API_URL = "http://localhost:8000/api/v1"
ITEM_NAME = "TEST_DELETE_ITEM"

def p(msg):
    print(f"[Verify] {msg}")

def main():
    p("Starting Delete Feature Verification...")
    
    # 1. Register a test item (or ingest data to auto-create)
    p(f"1. Creating item {ITEM_NAME} via Ingest")
    requests.post(f"{API_URL}/data/ingest", json={
        "item_name": ITEM_NAME,
        "item_type": "parameter",
        "value": 0.55,
        "uph": 100
    })
    
    # Check it exists
    res = requests.get(f"{API_URL}/configs")
    configs = res.json()["item_configs"]
    if ITEM_NAME in configs:
        p(f"   -> Item {ITEM_NAME} created successfully.")
    else:
        p(f"   -> FAILURE: Item {ITEM_NAME} not found after ingest.")
        return

    # 2. Delete the item
    p(f"2. Deleting item {ITEM_NAME}")
    res = requests.delete(f"{API_URL}/configs/{ITEM_NAME}")
    if res.status_code == 200:
        p("   -> Delete request successful.")
    else:
        p(f"   -> Delete failed: {res.text}")
        return
        
    # 3. Verify deletion
    p(f"3. Verifying deletion...")
    res = requests.get(f"{API_URL}/configs")
    configs = res.json()["item_configs"]
    if ITEM_NAME not in configs:
        p(f"   -> SUCCESS: Item {ITEM_NAME} is gone.")
    else:
        p(f"   -> FAILURE: Item {ITEM_NAME} still exists!")

if __name__ == "__main__":
    main()
