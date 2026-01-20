import requests
import json
import time
import random

BASE_URL = "http://localhost:8000"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def test_health():
    try:
        resp = requests.get(f"{BASE_URL}/health")
        log(f"Health Check: {resp.status_code} - {resp.json()}")
        return True
    except Exception as e:
        log(f"Health Check Failed: {e}")
        return False

def push_data(item_name, item_type, value, uph, metadata=None):
    payload = {
        "item_name": item_name,
        "item_type": item_type,
        "value": value,
        "uph": uph,
        "meta_data": metadata or {},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/data/ingest", json=payload)
        return resp.json()
    except Exception as e:
        log(f"Push Failed: {e}")
        return None

def run_simulation():
    item_name = "DEMO_YIELD_01"
    
    log("=== 开始模拟演练 ===")
    
    # 1. 注册项目 (可选，系统会自动注册默认值)
    log("1. 注册新监控项...")
    requests.post(f"{BASE_URL}/api/v1/items/register", json={
        "item_name": item_name,
        "item_type": "yield",
        "mu0": 0.0005,
        "base_uph": 500
    })
    
    # 2. 推送正常数据 (积累历史)
    log("2. 推送 5 个正常周期数据 (建立背景)...")
    for i in range(5):
        val = 0.0005 + random.uniform(-0.0001, 0.0001)
        resp = push_data(item_name, "yield", val, 500)
        # print(f"   Cycle {i+1}: Alert={resp.get('alert')}")
        time.sleep(0.1)

    # 3. 触发异常 (大异常，应该立即报警)
    log("3. 连续注入异常数据 (不良率飙升至 0.05)...")
    last_resp = {}
    for i in range(10):
        resp_alert = push_data(item_name, "yield", 0.05, 500)
        # log(f"   Cycle {i+1}: Alert={resp_alert.get('alert')}, CUSUM={resp_alert.get('current_status', {}).get('S_plus')}")
        if resp_alert.get('alert'):
            last_resp = resp_alert
            log(f"   -> 🚨 在第 {i+1} 次尝试时触发报警！")
            break
        time.sleep(0.1)
    else:
        log("   ❌ 10次尝试均未触发报警。")

    log(f"   -> 最终报警状态: {last_resp.get('alert')}")
    log(f"   -> 推送执行: {last_resp.get('push')}")
    
    if last_resp.get('alert') and last_resp.get('push'):
        log("   ✅ 成功检测到异常并触发推送！")
    else:
        log("   ❌ 未触发报警或推送，请检查逻辑！")

    # 4. 验证报警抑制 (冷却期)
    log("4. 再次注入相同异常 (验证冷却期)...")
    resp_cooldown = push_data(item_name, "yield", 0.05, 500)
    log(f"   -> 报警状态: {resp_cooldown.get('alert')} (预期: True)")
    log(f"   -> 推送执行: {resp_cooldown.get('push')} (预期: False - 被抑制)")
    
    if resp_cooldown.get('alert') and not resp_cooldown.get('push'):
        log("   ✅ 报警抑制生效！系统检测到异常但未重复推送。")
    else:
        log("   ❌ 报警抑制验证失败。")

    # 5. 验证参数类双边监控
    log("5. 验证设备参数双向监控 (Temperature)...")
    param_item = "DEMO_TEMP_01"
    # 注册参数项
    requests.post(f"{BASE_URL}/api/v1/items/register", json={
        "item_name": param_item,
        "item_type": "parameter",
        "mu0": 25.0,
        "base_uph": 1 # 参数类通常一次测一个
    })
    # 此处假设系统已经有足够的历史数据来计算 std，或者使用了默认 std=1.0
    # 我们的代码里 k_updater.get_current_std 默认会返回 None -> 1.0 (兜底)
    # 注入一个极大的值
    resp_param = push_data(param_item, "parameter", 50.0, 1) # 25 -> 50, 偏差25
    log(f"   -> 参数异常推送: {resp_param.get('push')}")
    side = resp_param.get('current_status', {}).get('calculation_details', {}).get('alert_side')
    log(f"   -> 报警方向: {side} (预期: upper)")

    log("=== 演练结束 ===")

if __name__ == "__main__":
    # 等待服务启动
    for _ in range(5):
        if test_health():
            break
        time.sleep(1)
    else:
        log("无法连接到服务，请确认服务已启动。")
        exit(1)
        
    run_simulation()
