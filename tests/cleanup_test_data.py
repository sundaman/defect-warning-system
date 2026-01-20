import requests
import json

BASE_URL = "http://localhost:8000"

def delete_test_items():
    url = f"{BASE_URL}/api/v1/configs/batch-delete"
    # Delete both the simple key and the composite key created during testing
    items_to_delete = [
        "TEST_META_ITEM_001",
        "test_prod::test_line::test_station::TEST_META_ITEM_001"
    ]
    
    payload = {"items": items_to_delete}
    
    try:
        response = requests.post(url, json=payload)
        print("Delete Response:", response.json())
    except Exception as e:
        print(f"Delete failed: {e}")

if __name__ == "__main__":
    delete_test_items()
