import numpy as np
import matplotlib.pyplot as plt
import os

def calculate_threshold_multiplier(uph, base_uph, min_uph_ratio=0.5, penalty_strength=1.0):
    """
    计算给定 UPH 下的阈值放大倍数 (Multiplier)
    
    Args:
        uph: 当前 UPH
        base_uph: 基准 UPH
        min_uph_ratio: 触发额外惩罚的比例阈值 (默认 0.5)
        penalty_strength: 惩罚强度系数 (1.0 = 原算法, 越小越宽松)
    """
    if uph <= 0:
        return np.nan
        
    uph_ratio = uph / base_uph
    
    # 基础物理放大 (1/sqrt(n) 规律)
    # 当 UPH < Base 时，样本量减少，波动自然增大，需要基础放大
    if uph_ratio >= 1:
        base_multiplier = 1.0
    else:
        base_multiplier = np.sqrt(1 / uph_ratio)
        
    # 额外惩罚项 (应对低产时的非正态剧烈波动)
    extra_penalty = 0.0
    if uph_ratio < min_uph_ratio:
        # 原公式: sqrt(min_ratio / ratio - 1)
        # 引入 penalty_strength 系数控制力度
        raw_penalty = np.sqrt(min_uph_ratio / uph_ratio - 1)
        extra_penalty = penalty_strength * raw_penalty
        
    return base_multiplier * (1 + extra_penalty)

def visualize_strategies():
    base_uph = 500
    min_uph_ratio = 0.5
    min_detection_uph = 50 # 0.1 * 500
    
    # 生成 UPH 序列 (从 50 到 600)
    uphs = np.linspace(min_detection_uph, 600, 500)
    
    # 定义不同策略
    strategies = [
        {"name": "High Penalty (Original)", "strength": 1.0, "color": "#FF4B4B", "style": "-"},
        {"name": "Medium Penalty (New)",   "strength": 0.6, "color": "#FFA500", "style": "--"},
        {"name": "Low Penalty (New)",      "strength": 0.3, "color": "#4CAF50", "style": "-."}
    ]
    
    plt.figure(figsize=(12, 7))
    
    # 绘制每条曲线
    for strat in strategies:
        multipliers = [calculate_threshold_multiplier(u, base_uph, min_uph_ratio, strat["strength"]) for u in uphs]
        plt.plot(uphs, multipliers, label=f"{strat['name']} (k={strat['strength']})", 
                 color=strat['color'], linestyle=strat['style'], linewidth=2.5)

    # 绘制辅助线和区域
    plt.axvline(x=base_uph, color='gray', linestyle=':', alpha=0.5, label='Base UPH (500)')
    plt.axvline(x=base_uph * min_uph_ratio, color='blue', linestyle=':', alpha=0.5, label='Penalty Start (250)')
    
    # 标注区域
    plt.axvspan(0, base_uph * min_uph_ratio, color='gray', alpha=0.1, label='Low UPH Zone')
    
    # 设置图表属性
    plt.title(f"Dynamic Threshold Multiplier vs UPH\n(Comparing Penalty Strategies)", fontsize=14)
    plt.xlabel("Current UPH", fontsize=12)
    plt.ylabel("Threshold Multiplier (Base = 1.0)", fontsize=12)
    plt.grid(True, which='both', linestyle='--', alpha=0.7)
    plt.legend(loc='upper right', frameon=True, framealpha=0.9)
    
    # 添加注解
    plt.text(100, 8, "Penalty Zone\nMultiplier rises non-linearly", fontsize=10, color='blue')
    plt.text(400, 1.5, "Standard Zone\nMultiplier = 1.0", fontsize=10, color='green')
    
    # 保存图片
    output_path = "uph_strategy_comparison.png"
    plt.savefig(output_path, dpi=120, bbox_inches='tight')
    print(f"Chart saved to {os.path.abspath(output_path)}")

if __name__ == "__main__":
    visualize_strategies()
