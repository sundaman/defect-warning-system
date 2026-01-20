import csv
import requests
import datetime
import time
import sys
import os

CSV_PATH = "/Users/luxsan-ict/.opencode/Defect Early Warning/data/generated/defect_test_data_v2.csv"
BASE_URL = "http://127.0.0.1:8000"

def register_item(item_name):
    print(f"[*] Registering item: {item_name}")
    payload = {
        "item_name": item_name,
        "item_type": "yield",
        "mu0": 0.002,      # Based on CSV data approx mean
        "base_uph": 500,
        "penalty_strength": 1.0,
        "cooldown_periods": 6
    }
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/items/register", json=payload)
        # resp.raise_for_status() 
        print(f"    -> Response: {resp.json()}")
    except Exception as e:
        print(f"    -> Register Warning: {e}")

def import_data():
    print(f"[*] Reading CSV from: {CSV_PATH}")
    
    if not os.path.exists(CSV_PATH):
        print(f"Error: File not found at {CSV_PATH}")
        return

    success_count = 0
    fail_count = 0
    
    with open(CSV_PATH, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        print(f"[*] Found {len(rows)} rows. Starter processing...")
        
        # Determine unique items and register them
        unique_items = set(row['error_code'] for row in rows) # Assuming error_code is item_name
        # Or construct name like S01_CODE
        # Let's stick to using 'error_code' as item_name for simplicity, or prepend station if needed.
        # Looking at CSV: station_id=S01, error_code=CABLE_TEAR_3_1. 
        # Let's use `S01_<CODE>` as name to be safe? 
        # The user's CSV has `S01` and `CABLE_TEAR_3_1`.
        # Let's use `CABLE_TEAR_3_1` directly as per previous context? 
        # Wait, usually we want unique names. Let's use row['error_code'] directly for now.
        
        for item in unique_items:
            register_item(item)
            
        for i, row in enumerate(rows):
            try:
                # 1. Parse and Shift Time
                orig_time_str = row['timestamp']
                dt = datetime.datetime.fromisoformat(orig_time_str)
                
                # Shift +2 Years
                # handling leap years roughly (just replace year)
                try:
                    new_dt = dt.replace(year=dt.year + 2)
                except ValueError: 
                    # Handle Feb 29 on non-leap year target?
                    # 2024 (Leap) -> 2026 (Non-Leap). Feb 29 -> Error.
                    # Fallback to Feb 28
                    new_dt = dt.replace(year=dt.year + 2, day=28)
                
                new_time_str = new_dt.isoformat()
                
                # 2. Construct Payload
                # item_name_db = f"{row['station_id']}_{row['error_code']}" 
                # Let's just use error_code as requested implies "this csv data".
                item_name = row['error_code']
                
                payload = {
                    "item_name": item_name,
                    "item_type": "yield",
                    "value": float(row['defect_rate']),
                    "uph": int(row['current_uph']),
                    "timestamp": new_time_str,
                    "meta_data": {
                        "station": row['station_id'],
                        "line": "L1", # Mock
                        "product": "ProductA", # Mock
                        "imported_from_csv": True,
                        "original_time": orig_time_str
                    }
                }
                
                # 3. Post
                resp = requests.post(f"{BASE_URL}/api/v1/data/ingest", json=payload)
                if resp.status_code == 200:
                    success_count += 1
                else:
                    fail_count += 1
                    if i % 100 == 0: print(f"Row {i} failed: {resp.text}")

                if i % 500 == 0:
                    print(f"    Processed {i}/{len(rows)} | Success: {success_count} | Fail: {fail_count}")

            except Exception as e:
                print(f"Error on row {i}: {e}")
                fail_count += 1
                
    print(f"[*] Import Complete. Total Success: {success_count}, Total Failed: {fail_count}")

if __name__ == "__main__":
    import_data()
