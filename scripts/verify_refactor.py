
import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

def print_result(test_name, success, message=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"[{status}] {test_name}: {message}")

def verify_refactor():
    print(">>> Starting Verification for Global Config Refactor & Guided Import...\n")

    # 1. Setup: Ensure we have an existing item (S01_TEST_EXISTING)
    item_existing = "S01_TEST_EXISTING"
    requests.post(f"{BASE_URL}/configs/{item_existing}", json={
        "mu0": 0.5, "base_uph": 1000, "monitoring_side": "upper", "target_shift_sigma": 1.0 # Initial state
    })
    
    # 2. Modify Global Config (Default Policy)
    print("--- Testing Default Policy Isolation ---")
    new_global_defaults = {
        "target_shift_sigma": 5.5, # Distinct value
        "target_arl0": 999,
        "cooldown_periods": 20,
        "monitoring_side": "lower"
    }
    requests.put(f"{BASE_URL}/configs/global", json=new_global_defaults)
    
    # Check if existing item was affected (Should NOT be affected)
    # How to check? usage of get_all_configs or get specific item config
    # Actually, the API doesn't expose the *active* detector internal state easily, 
    # but we can check the stored config via /api/v1/configs
    
    # Wait a bit for async stuff if any (though logic is sync now)
    time.sleep(1)
    
    res = requests.get(f"{BASE_URL}/configs")
    all_configs = res.json()["item_configs"]
    global_defaults = res.json()["global_defaults"]
    
    # Check global defaults updated
    is_global_updated = global_defaults["target_shift_sigma"] == 5.5
    print_result("Global Config Updated", is_global_updated, f"Current: {global_defaults['target_shift_sigma']}")

    # Check existing item UNCHANGED (It might depend on how we stored it initially. 
    # If we created it without explicit params, it might use defaults? 
    # No, set_item_config stores what is passed. 
    # But wait, create via POST /configs overwrites. 
    # Let's check what the existing item has.)
    existing_conf = all_configs.get(item_existing, {})
    # It should retain its original or None values? 
    # Actually manager logic: if item_config has value, use it. If not, fallback.
    # But main.py update_global_config NO LONGER propagates.
    # So if we didn't store explicit values for the existing item, manager would previously fallback.
    # But manager *reads* from self.global_config for fallbacks.
    # self.global_config IS updated by update_global_config.
    # So actually... if the item config doesn't have explicit values, it WILL see the new default.
    # But typically set_item_config stores explicit keys?
    # Our batch import stores explicit keys now.
    # The register endpoint stores explicit keys.
    # So most items should have explicit keys.
    
    # Let's verify Guided Import (Batch Import with Overrides)
    print("\n--- Testing Guided Import ---")
    item_new = "S01_TEST_GUIDED_IMPORT"
    
    # Import with overrides DIFFERENT from Global Defaults
    # Global Default Shift is 5.5 (set above)
    override_config = {
        "target_shift_sigma": 2.0, # Override
        "monitoring_side": "upper"
    }
    
    req_body = {
        "items": [item_new],
        "config": override_config
    }
    
    requests.post(f"{BASE_URL}/items/batch-import", json=req_body)
    
    # Verify the new item has the override value (2.0), NOT the global default (5.5)
    res = requests.get(f"{BASE_URL}/configs")
    all_configs = res.json()["item_configs"]
    new_item_conf = all_configs.get(item_new, {})
    
    actual_sigma = new_item_conf.get("target_shift_sigma")
    success_import = actual_sigma == 2.0
    print_result("Guided Import Override", success_import, f"Expected 2.0, Got {actual_sigma}")
    if not success_import:
        print(f"Debug: Global Default was {global_defaults['target_shift_sigma']}")

    # Verify standard import (no overrides) uses Global Default
    print("\n--- Testing Standard Import (Defaults) ---")
    item_std = "S01_TEST_STD_IMPORT"
    requests.post(f"{BASE_URL}/items/batch-import", json={"items": [item_std]})
    
    res = requests.get(f"{BASE_URL}/configs")
    all_configs = res.json()["item_configs"]
    std_item_conf = all_configs.get(item_std, {})
    
    # It should have 'baked in' the global default (5.5)
    actual_std_sigma = std_item_conf.get("target_shift_sigma")
    success_std = actual_std_sigma == 5.5
    print_result("Standard Import Uses Default", success_std, f"Expected 5.5, Got {actual_std_sigma}")

if __name__ == "__main__":
    try:
        verify_refactor()
    except Exception as e:
        print(f"❌ Error: {e}")
