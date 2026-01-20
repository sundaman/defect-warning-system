import requests
import time
import json

BASE_URL = "http://localhost:8000/api/v1"
ITEM_NAME = "TEST_HOT_RELOAD_01"

def p(msg):
    print(f"[Verify] {msg}")

def get_latest_record(item_name):
    # Fetch history limit 1
    resp = requests.get(f"{BASE_URL}/history", params={"item_name": item_name, "limit": 1})
    resp.raise_for_status()
    data = resp.json()
    return data[0] if data else None

def set_global_config(shift, arl0):
    payload = {
        "target_shift_sigma": shift,
        "target_arl0": arl0
    }
    resp = requests.put(f"{BASE_URL}/configs/global", json=payload)
    resp.raise_for_status()
    data = resp.json()
    if "debug_info" in data:
        p(f"   [DEBUG_API] {data['debug_info']}")
    return data

def ingest_data(value, timestamp):
    payload = {
        "item_name": ITEM_NAME,
        "item_type": "yield",
        "value": value,
        "uph": 3600,
        "timestamp": timestamp,
        "meta_data": {"station": "TEST", "product": "DEMO"}
    }
    resp = requests.post(f"{BASE_URL}/data/ingest", json=payload)
    resp.raise_for_status()

def main():
    p(f"Target Item: {ITEM_NAME}")
    
    # 1. Reset Global Config to Standard
    p("1. Setting Global Config to Standard: Shift=1.0, ARL0=250")
    set_global_config(1.0, 250.0)
    
    # 2. Ingest Data Point 1
    t1 = "2026-01-01T10:00:00"
    p(f"2. Ingesting Data Point 1 (Val=0.99) at {t1}")
    ingest_data(0.99, t1)
    
    # 3. Check Threshold h
    rec = get_latest_record(ITEM_NAME)
    h1 = None
    if rec:
        h_val = rec.get("h_value")
        ts = rec.get("timestamp")
        p(f"   -> Result: h_value = {h_val:.4f}, Timestamp = {ts}")
        h1 = h_val
    
    # 4. Change Global Config (Make it less sensitive, larger h)
    # Increasing ARL0 should increase h
    p("4. Updating Global Config (Hot Reload): Shift=1.0, ARL0=1000 (Expect higher threshold)")
    set_global_config(1.0, 1000.0)
    
    # 5. Ingest Data Point 2
    # Use exact same value to keep other variables constant
    t2 = "2026-01-01T10:01:00"
    p(f"5. Ingesting Data Point 2 (Val=0.99) at {t2}")
    ingest_data(0.99, t2)
    
    # 6. Check Threshold h again
    rec = get_latest_record(ITEM_NAME)
    if rec:
        h2 = rec.get("h_value")
        ts = rec.get("timestamp")
        p(f"   -> Result: h_value = {h2:.4f}, Timestamp = {ts}")
    else:
        h2 = None
        
    if h2 is not None and h1 is not None:
        if abs(h2 - h1) > 0.1:
            p("SUCCESS: Threshold changed immediately without server restart!")
            p(f"Difference: {h1:.4f} -> {h2:.4f}")
        else:
            p("FAILURE: Threshold did not change significantly.")
    else:
        p("FAILURE: Could not retrieve one or both h values for comparison.")

if __name__ == "__main__":
    main()
