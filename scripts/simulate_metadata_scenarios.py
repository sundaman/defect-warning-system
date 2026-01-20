import requests
import random
import time
import numpy as np
from datetime import datetime, timedelta
import json

BASE_URL = "http://localhost:8000/api/v1"

# === Configuration ===
SCENARIOS = [
    {
        "id": "1_Strict_Normal",
        "meta": {"product": "Phone15", "line": "L1", "station": "SMT"},
        "item_name": "Volt_3V3",
        "config": {"target_shift_sigma": 1.5, "target_arl0": 1000, "monitoring_side": "both", "penalty_strength": 1.0},
        "simulation": {"base_mean": 3.3, "std": 0.05, "uph": 500, "anomaly": None}
    },
    {
        "id": "2_Relaxed_Noise",
        "meta": {"product": "Phone15", "line": "L2", "station": "SMT"},
        "item_name": "Volt_3V3",
        "config": {"target_shift_sigma": 2.0, "target_arl0": 200, "monitoring_side": "both", "penalty_strength": 0.3},
        "simulation": {"base_mean": 3.3, "std": 0.15, "uph": 500, "anomaly": None}
    },
    {
        "id": "3_Watch_Drop",
        "meta": {"product": "Watch9", "line": "L1", "station": "Audio"},
        "item_name": "MIC_TEST",
        "config": {"target_shift_sigma": 1.5, "monitoring_side": "lower"},
        "simulation": {"base_mean": 80.0, "std": 1.0, "uph": 450, "anomaly": "sudden_drop"}
    },
    {
        "id": "4_Watch_Drift",
        "meta": {"product": "Watch9", "line": "L1", "station": "Audio"},
        "item_name": "SPK_TEST",
        "config": {"target_shift_sigma": 1.2, "monitoring_side": "upper"},
        "simulation": {"base_mean": 90.0, "std": 0.5, "uph": 450, "anomaly": "drift"}
    },
    {
        "id": "5_Pad_LowUPH",
        "meta": {"product": "PadPro", "line": "L3", "station": "Screen"},
        "item_name": "COLOR_X",
        "config": {"base_uph": 500, "penalty_strength": 1.0},
        "simulation": {"base_mean": 0.5, "std": 0.01, "uph": 50, "anomaly": None} # Very low UPH
    }
]

DATA_POINTS = 500
START_TIME = datetime.now() - timedelta(hours=DATA_POINTS // 60 + 2) # Assume 1 point per hour or min? Let's do 1 per minute for speed

def register_items():
    print("\n=== 1. Registering Detectors ===")
    for s in SCENARIOS:
        payload = {
            "items": [s["item_name"]],
            "meta_data": s["meta"],
            "config": s["config"]
        }
        try:
            resp = requests.post(f"{BASE_URL}/items/batch-import", json=payload)
            resp.raise_for_status()
            print(f"✅ Registered: {s['meta']['product']}::{s['meta']['line']}::{s['item_name']}")
        except Exception as e:
            print(f"❌ Failed to register {s['id']}: {e}")

def simulate_data():
    print("\n=== 2. Ingesting Simulation Data ===")
    
    for s in SCENARIOS:
        print(f"--> Simulating {s['id']}...")
        current_time = START_TIME
        sim_conf = s["simulation"]
        base_mean = sim_conf["base_mean"]
        base_std = sim_conf["std"]
        base_uph = sim_conf["uph"]
        anomaly_type = sim_conf["anomaly"]
        
        for i in range(DATA_POINTS):
            # 1. Generate value
            val = np.random.normal(base_mean, base_std)
            
            # Anomaly Injection logic (at around 70% of progress)
            if i > DATA_POINTS * 0.7:
                if anomaly_type == "sudden_drop":
                     val -= (base_std * 5) # 5 sigma drop
                elif anomaly_type == "drift":
                     drift_factor = (i - DATA_POINTS * 0.7) * 0.05
                     val += drift_factor * base_std
            
            # 2. Add UPH noise
            curr_uph = int(base_uph * random.uniform(0.9, 1.1))
            
            # 3. Payload
            payload = {
                "item_name": s["item_name"],
                "item_type": "parameter",
                "value": val,
                "uph": curr_uph,
                "timestamp": current_time.isoformat(),
                "meta_data": s["meta"]
            }
            
            # 4. Send (Batch or single? Single for simplicity to hit exact endpoint logic)
            # To speed up, we could use concurrent futures, but strict ordering by time is better for CUSUM
            try:
                resp = requests.post(f"{BASE_URL}/data/ingest", json=payload)
                # Don't print every line
                if i % 100 == 0:
                    print(f"    Set {i}/{DATA_POINTS} ingest ok.")
            except Exception as e:
                print(f"    Ingest failed at {i}: {e}")
            
            current_time += timedelta(minutes=1)

def print_summary():
    print("\n=== 3. Simulation Complete ===")
    print("Please check the Dashboard for the following Metadata Contexts:")
    print("-" * 60)
    print(f"{'Product':<12} | {'Line':<8} | {'Station':<10} | {'Item Name':<15} | {'Scenario Note'}")
    print("-" * 60)
    for s in SCENARIOS:
        m = s["meta"]
        print(f"{m['product']:<12} | {m['line']:<8} | {m['station']:<10} | {s['item_name']:<15} | {s['id']}")
    print("-" * 60)

if __name__ == "__main__":
    register_items()
    simulate_data()
    print_summary()
