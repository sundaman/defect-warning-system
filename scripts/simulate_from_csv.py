import pandas as pd
import requests
import time
import sys
import os

# 配置
API_URL = "http://127.0.0.1:8000"
CSV_FILE = "/Users/luxsan-ict/.opencode/Defect Early Warning/data/generated/defect_test_data_v2.csv"

def wait_for_server():
    print("Waiting for API server to start...")
    for _ in range(10):
        try:
            requests.get(f"{API_URL}/health")
            print("API Server is UP!")
            return True
        except:
            time.sleep(1)
    return False

def run_simulation():
    if not os.path.exists(CSV_FILE):
        print(f"Error: CSV file not found at {CSV_FILE}")
        return

    print(f"Loading data from {CSV_FILE}...")
    df = pd.read_csv(CSV_FILE)
    
    # 1. 注册 Item
    # 假设还是验证 DUMMY_S01 (根据 CSV，其实是 station_id + error_code)
    # 我们先取第一行看看结构
    first_row = df.iloc[0]
    item_name = f"{first_row['station_id']}_{first_row['error_code']}"
    
    print(f"Registering Item: {item_name}")
    try:
        requests.post(f"{API_URL}/api/v1/items/register", json={
            "item_name": item_name,
            "item_type": "yield",
            "mu0": 0.0005,      # 初始值设小一点，让它 adaptive
            "base_uph": 500,
            "penalty_strength": 0.6, # 设定为 Medium
            "cooldown_periods": 6    # 设定冷却期
        })
    except Exception as e:
        print(f"Failed to register item: {e}")
        return

    print(f"Starting ingestion of {len(df)} rows...")
    
    success_count = 0
    match_count = 0
    
    # 为了演示效果，我们不 sleep 太多，但也别太快挂了
    # 另外，因为要看 Dashboard，我们可能希望把时间"搬运"到今天？
    # 不，Dashboard 支持历史查询，我们直接用 CSV 的原始时间戳即可。
    # API 已经支持接收 timestamp。
    
    session = requests.Session()
    
    start_time = time.time()
    
    for idx, row in df.iterrows():
        # 简单解析: S01_CABLE_TEAR -> station=S01, product=Phone, line=L01
        parts = item_name.split('_')
        station = parts[0] if len(parts) > 0 else "Unknown"
        
        payload = {
            "item_name": item_name,
            "item_type": "yield",
            "value": row['defect_rate'],
            "uph": int(row['current_uph']),
            "timestamp": row['timestamp'],
            "meta_data": {
                "source": "csv_replay", 
                "station": station,
                "product": "Phone15",  # 模拟
                "line": "L01"        # 模拟
            }
        }
        
        try:
            resp = session.post(f"{API_URL}/api/v1/data/ingest", json=payload)
            # resp.raise_for_status()
            res_data = resp.json()
            
            my_alert = res_data['alert']
            expected_alert = str(row['alarm_type']).upper() == 'TRUE'
            
            if my_alert == expected_alert:
                match_count += 1
            
            success_count += 1
            
            # 每 500 条打印一次进度
            if idx % 500 == 0:
                print(f"[{idx}/{len(df)}] Processed. Match Rate: {match_count/(idx+1):.2%}")
                
        except Exception as e:
            print(f"Request failed at row {idx}: {e}")
            
    end_time = time.time()
    duration = end_time - start_time
    print(f"\nSimulation Completed in {duration:.2f}s ({len(df)/duration:.1f} req/s)")
    print(f"Total: {len(df)}, Success: {success_count}")
    print(f"Consistency Match: {match_count}/{len(df)} ({match_count/len(df):.2%})")
    print(f"\n✅ Data is now populated in database.")
    print(f"👉 Please open Dashboard to view: {API_URL}/")
    print(f"   Enter Item Name: {item_name}")
    print(f"   (You may not need date range if using 'select all', or set range around {df.iloc[0]['timestamp']})")

if __name__ == "__main__":
    if wait_for_server():
        run_simulation()
    else:
        print("Server failed to start.")
