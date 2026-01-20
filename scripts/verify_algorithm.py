import pandas as pd
import sys
import os
import datetime

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.core.manager import DetectionEngineManager

def verify_consistency(csv_path):
    print(f"Loading test data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # 初始化引擎 (关闭冷却期以验证原始算法输出)
    config = {
        "target_shift_sigma": 1.0,
        "target_arl0": 250.0,
        "enable_cooldown": False 
    }
    manager = DetectionEngineManager(config)
    
    total_points = 0
    match_points = 0
    false_positives = 0
    false_negatives = 0
    
    results = []
    
    print("Starting simulation...")
    for idx, row in df.iterrows():
        # 构造 Item Name
        item_name = f"{row['station_id']}_{row['error_code']}"
        
        # 转换时间戳
        # CSV format: 2023-08-20T08:00:00
        timestamp = row['timestamp']
        
        # 执行检测
        # 注意: 这里的 mu0 和 base_uph 需要与算法团队生成数据时的一致
        # 通常测试数据的 mu0 = 前几百个点的均值，或者预设值
        # 既然没有额外信息，我们假设引擎会自适应初始化 (detector 默认 mu0=0.0005)
        # 为了更准确，我们应该在 CSV 中寻找这些信息，或者让 detector 能够快速热身
        # 这里的 CSV 有 defect_rate，我们可以用前 N 个点的均值作为 mu0 如果需要
        # 但 AdaptiveCUSUMDetector 有自适应能力
        
        # 临时策略：对于第一个点，强制设置 mu0 为该 Item 的初始 defect_rate (如果非0) 或者全局默认
        # 或者 trust the adaptation.
        
        # 实际上，manager.process_data 内部写死了 mu0=0.0005 (在 get_or_create_detector 中)
        # 如果测试数据的真实 mu 差别很大，这会影响结果
        # 让我们先让它跑起来，看看偏差
        
        # 必须传入 item_type="yield"
        res = manager.process_data(
            item_name=item_name,
            item_type="yield",
            value=row['defect_rate'],
            uph=row['current_uph'], # 使用 current_uph
            timestamp=timestamp,
            metadata={"row_id": idx}
        )
        
        my_alert = res['alert']
        expected_alert = str(row['alarm_type']).upper() == "TRUE"
        
        if my_alert == expected_alert:
            match_points += 1
        else:
            if my_alert and not expected_alert:
                false_positives += 1
            else:
                false_negatives += 1
            
            # 记录不匹配的点
            results.append({
                "index": idx,
                "timestamp": timestamp,
                "value": row['defect_rate'],
                "my_alert": my_alert,
                "expected": expected_alert,
                "current_baseline": res['current_status']['baseline'],
                "cusum_score": res['current_status']['S_plus'],
                "threshold": res['current_status']['h_value']
            })
            
        total_points += 1
        
        if idx % 1000 == 0:
            print(f"Processed {idx} rows...")

    accuracy = match_points / total_points if total_points > 0 else 0
    print("\n=== Verification Report ===")
    print(f"Total Points: {total_points}")
    print(f"Matches: {match_points} ({accuracy:.2%})")
    print(f"False Positives (我是报警/数据未标): {false_positives}")
    print(f"False Negatives (我未报/数据已标): {false_negatives}")
    
    if results:
        print("\nTop 10 Mismatches:")
        for r in results[:10]:
            print(r)
            
    # 输出详细 CSV 供分析
    if results:
        out_df = pd.DataFrame(results)
        out_df.to_csv("verification_mismatches.csv", index=False)
        print(f"\nMismatches saved to verification_mismatches.csv")

if __name__ == "__main__":
    csv_file = "/Users/luxsan-ict/.opencode/Defect Early Warning/data/generated/defect_test_data_v2.csv"
    verify_consistency(csv_file)
