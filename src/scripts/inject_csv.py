import csv
import os
import sys
from datetime import datetime
from collections import defaultdict
import numpy as np

# Adjust path to import src
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from src.core.manager import DetectionEngineManager
from src.utils.persistence import ConfigStore
from src.db.database import engine, Base, DB_DIR

# CSV Path
CSV_PATH = "/Users/luxsan-ict/.opencode/Defect Early Warning/data/generated/defect_test_data_v2.csv"

def inject_data():
    if not os.path.exists(CSV_PATH):
        print(f"Error: CSV file not found at {CSV_PATH}")
        return

    print("Resetting Database...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Init Manager and Store
    config_path = os.path.join(DB_DIR, "item_configs.json")
    config_store = ConfigStore(config_path)
    
    # We want to clear old configs too to be clean
    # But ConfigStore logic just loads from file. We can manually empty it or just overwrite.
    # To be safe, let's just overwrite keys we find.
    
    manager = DetectionEngineManager(global_config={
        "enable_cooldown": True, 
        "cooldown_periods": 5,
        "monitoring_side": "upper"
    })

    print(f"Reading data from {CSV_PATH}...")
    
    rows = []
    items_meta = set()
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
            items_meta.add((row['error_code'], row['station_id']))

    print(f"Found {len(rows)} records covering {len(items_meta)} items.")

    # 1. Register Configs
    print("Registering Detectors...")
    for item_name, station in items_meta:
        # Generate metadata
        meta = {
            "station": station,
            "product": "TestProduct", # Default
            "line": "L1" # Default
        }
        
        # Determine defaults (Simulation usually implies low defect rate)
        # We can set mu0 to 0.001
        config = {
            "mu0": 0.001,
            "base_uph": 500,
            "target_shift_sigma": 1.5, # Sensitive enough for testing
            "monitoring_side": "upper",
            "item_type": "measurement", # It's defect rate, so technically yield-like, but system treats as scalar value
            "meta_data": meta
        }
        
        key = manager._generate_detector_key(item_name, meta)
        config_store.set_item_config(key, config)
        # Also saving simple key for UI
        config_store.set_item_config(item_name, config)
        print(f"  Registered {item_name} @ {station}")

    # 2. Inject Data
    print("Injecting Data...")
    
    # Sort rows by timestamp just in case
    rows.sort(key=lambda x: x['timestamp'])
    
    # Shift Timestamps to end at NOW
    # Assuming rows are roughly hourly or sequential
    now = datetime.now()
    # If 10000 records, shift so last one is near now
    # But we need to preserve relative intervals.
    # Easy way: Calculate offset.
    last_ts_str = rows[-1]['timestamp']
    # Parse format: 2023-08-20T08:00:00 (from head output)
    try:
        last_ts = datetime.fromisoformat(last_ts_str)
    except ValueError:
        # Fallback if format is different
        last_ts = datetime.strptime(last_ts_str, "%Y-%m-%dT%H:%M:%S")
        
    time_offset = now - last_ts
    print(f"Time Shifting by {time_offset} to bring data to present.")

    count = 0
    from datetime import timedelta
    
    for row in rows:
        item_name = row['error_code']
        station = row['station_id']
        val = float(row['defect_rate'])
        uph = int(float(row['current_uph'])) 
        
        orig_ts_str = row['timestamp']
        try:
           orig_ts = datetime.fromisoformat(orig_ts_str)
        except:
           orig_ts = datetime.strptime(orig_ts_str, "%Y-%m-%dT%H:%M:%S")
           
        new_ts = orig_ts + time_offset
        
        manager.process_data(
            item_name=item_name,
            item_type="measurement",
            value=val,
            uph=uph,
            timestamp=new_ts,
            metadata={
                "station": station,
                "product": "TestProduct",
                "line": "L1"
            },
            item_config={
                "mu0": 0.001,
                "base_uph": 500,
                "target_shift_sigma": 1.5,
                "monitoring_side": "upper" 
             }
        )
        count += 1
        if count % 500 == 0:
            print(f"  Processed {count}/{len(rows)}...", end='\r')

    # 3. Save State
    saved = manager.save_all_states()
    print(f"\n✅ Injection Complete. Saved {saved} item states.")

if __name__ == "__main__":
    inject_data()
