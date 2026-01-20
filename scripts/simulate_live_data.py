import requests
import time
import random
import datetime
import sys

BASE_URL = "http://127.0.0.1:8000"
ITEM_NAME = "DASHBOARD_TEST_ITEM_01"

def register_item():
    print(f"[*] Registering item: {ITEM_NAME}")
    payload = {
        "item_name": ITEM_NAME,
        "item_type": "yield",
        "mu0": 0.005,      # 0.5% defect rate baseline
        "base_uph": 1000,
        "penalty_strength": 0.6,
        "cooldown_periods": 5
    }
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/items/register", json=payload)
        resp.raise_for_status()
        print(f"    -> Success: {resp.json()}")
    except Exception as e:
        print(f"    -> Error: {e}")
        sys.exit(1)

def ingest_data(count=100):
    print(f"[*] Starting data ingestion ({count} points)...")
    
    # 模拟过去 5 小时的数据 (每 3 分钟一个点)
    start_time = datetime.datetime.now() - datetime.timedelta(minutes=count*3)
    
    for i in range(count):
        current_time = start_time + datetime.timedelta(minutes=i*3)
        timestamp = current_time.isoformat()
        
        # 模拟数据生成
        uph = int(random.normalvariate(1000, 50)) # UPH 波动
        
        # 前 80% 正常，后 20% 异常
        if i < count * 0.8:
            # 正常: 0.5% 左右波动
             defect_rate = max(0, random.normalvariate(0.005, 0.001))
        else:
            # 异常: 飙升到 2.0%
             defect_rate = max(0, random.normalvariate(0.02, 0.002))

        payload = {
            "item_name": ITEM_NAME,
            "item_type": "yield",
            "value": defect_rate,
            "uph": uph,
            "timestamp": timestamp,
            "meta_data": {"simulated": True}
        }
        
        try:
            resp = requests.post(f"{BASE_URL}/api/v1/data/ingest", json=payload)
            # resp.raise_for_status()
            data = resp.json()
            
            check_mark = "✅" if not data['alert'] else "🚨 ALERT!"
            print(f"    [{i+1}/{count}] Time: {timestamp[11:19]}Val: {defect_rate:.4f} | {check_mark}")
            
        except Exception as e:
            print(f"    -> Request Failed: {e}")
            
        time.sleep(0.05) # 快速注入

def verify_history():
    print(f"\n[*] Verifying History API...")
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/history", params={"item_name": ITEM_NAME, "limit": 10})
        data = resp.json()
        print(f"    -> Retrieved {len(data)} records from DB.")
        if len(data) > 0:
            print(f"    -> Latest record: {data[-1]['timestamp']} | Value: {data[-1]['value']}")
            print("    -> Database Integration Verification PASSED ✅")
        else:
            print("    -> Database seems empty ❌")
            
    except Exception as e:
        print(f"    -> Verification Failed: {e}")

def verify_dashboard_html():
    print(f"\n[*] Verifying Dashboard HTML Content...")
    try:
        resp = requests.get(f"{BASE_URL}/")
        if resp.status_code == 200 and "<title>Defect Warning Dashboard</title>" in resp.text:
             print("    -> Dashboard HTML is serving correctly ✅")
        else:
             print(f"    -> Dashboard HTML check failed (Status: {resp.status_code}) ❌")
    except Exception as e:
        print(f"    -> Dashboard check failed: {e}")

if __name__ == "__main__":
    # 等待 Server 启动
    time.sleep(2)
    register_item()
    ingest_data(count=60)
    verify_history()
    verify_dashboard_html()
