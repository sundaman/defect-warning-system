
import requests
import random
import time
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

def inject_test_data():
    current_time = datetime.now()
    url = f"{BASE_URL}/api/v1/data/ingest"
    
    # 模拟 5 个点，每个点有点波动，理论上 yield 的 std sqrt(p(1-p)/n) 应该 > 0
    # Baseline p=0.005, UPH=1000 -> std = sqrt(0.005*0.995/1000) ≈ 0.0022
    for i in range(5):
        payload = {
            "item_name": "S01_CABLE_TEAR_3_1",
            "item_type": "yield",
            "value": 0.006 + random.uniform(-0.001, 0.001), # slightly higher than baseline
            "uph": 1000,
            "timestamp": (current_time + timedelta(minutes=i*10)).isoformat(),
            "meta_data": {"station": "S01", "product": "Phone15", "line": "L01"}
        }
        try:
            resp = requests.post(url, json=payload)
            print(f"Sent: {payload['value']}, Status: {resp.status_code}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    time.sleep(2) # wait for server
    inject_test_data()
