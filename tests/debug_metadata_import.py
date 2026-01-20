import requests
import json
import os

BASE_URL = "http://localhost:8000"

def test_metadata_import():
    url = f"{BASE_URL}/api/v1/items/batch-import"
    
    payload = {
        "items": ["TEST_META_ITEM_001"],
        "config": {
            "target_shift_sigma": 2.0
        },
        "meta_data": {
            "product": "TEST_PROD",
            "station": "TEST_STATION",
            "line": "TEST_LINE"
        }
    }
    
    print(f"Sending payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Response:", response.json())
        
        # Verify persistence file directly
        config_path = "data/storage/item_configs.json"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                data = json.load(f)
                
            # Backend logic: key is composite if metadata provided
            # Expected Key format: product::line::station::item_name (lowercased in manager.py)
            expected_key = "test_prod::test_line::test_station::test_meta_item_001"
            
            if expected_key in data:
                print(f"SUCCESS: Found key '{expected_key}' in storage.")
                stored_meta = data[expected_key].get("meta_data")
                print("Stored Metadata:", stored_meta)
                if stored_meta and stored_meta.get("product") == "TEST_PROD":
                    print("SUCCESS: Metadata content matches.")
                else:
                    print("FAILURE: Metadata content mismatch or missing.")
            else:
                print(f"FAILURE: Key '{expected_key}' not found. Existing keys:")
                # print keys that look similar
                for k in data.keys():
                    if "test_meta" in k:
                        print(f" - {k}")
        else:
            print("FAILURE: Config file not found.")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_metadata_import()
