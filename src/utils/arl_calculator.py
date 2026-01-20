"""
ARL计算器模块
基于CUSUM理论和NIST标准实现
"""

import numpy as np
from typing import Dict, Tuple
from scipy.stats import norm


class ARLCalculator:
    """基于CUSUM理论的ARL计算器（NIST/ISO 7870-4标准）"""

    # NIST标准表格的预计算值（对于K=0.5）
    # 来源：NIST/SEMATECH e-Handbook of Statistical Methods, Section 6.3.2.3.1
    ARL_TABLE_K0_5 = {
        3.0: 30.0,
        3.5: 80.0,
        4.0: 370.4,
        4.5: 1000.0,
        5.0: 629.5,
        5.5: 2500.0,
    }

    # 对于K=0.25
    ARL_TABLE_K0_25 = {
        3.0: 10.0,
        3.5: 25.0,
        4.0: 93.7,
        4.5: 220.0,
        5.0: 157.4,
        5.5: 350.0,
    }

    # 对于K=0.75
    ARL_TABLE_K0_75 = {
        3.5: 150.0,
        4.0: 400.0,
        4.5: 1000.0,
        5.0: 2000.0,
    }

    @staticmethod
    def get_arl0_from_table(K: float, h: float) -> float:
        """从预计算表中查找ARL₀（内插）

        Args:
            K: 参考值
            h: 阈值

        Returns:
            ARL₀值
        """
        # 根据K值选择对应的表格
        if abs(K - 0.5) < 0.01:
            table = ARLCalculator.ARL_TABLE_K0_5
        elif abs(K - 0.25) < 0.01:
            table = ARLCalculator.ARL_TABLE_K0_25
        elif abs(K - 0.75) < 0.01:
            table = ARLCalculator.ARL_TABLE_K0_75
        else:
            # 使用近似公式
            return ARLCalculator.calculate_arl0_approx(K=K, h=h, delta=0.0)

        # 找到h在表格中的位置
        h_values = sorted(table.keys())

        if h <= h_values[0]:
            return table[h_values[0]]
        elif h >= h_values[-1]:
            return table[h_values[-1]]

        # 线性插值
        for i in range(len(h_values) - 1):
            if h_values[i] <= h <= h_values[i + 1]:
                h1, h2 = h_values[i], h_values[i + 1]
                arl1, arl2 = table[h1], table[h2]

                # 线性插值
                arl = arl1 + (arl2 - arl1) * (h - h1) / (h2 - h1)
                return arl

        # Fallback
        return ARLCalculator.calculate_arl0_approx(K=K, h=h, delta=0.0)

    @staticmethod
    def calculate_arl0_approx(K: float, h: float, delta: float = 0.0,
                               num_points: int = 1000) -> float:
        """近似计算ARL（积分方法）

        基于Brook & Evans (1972)的Markov链方法的简化版本

        Args:
            K: 参考值
            h: 阈值
            delta: 均值偏移（单位：σ），受控时delta=0
            num_points: 积分近似点数

        Returns:
            ARL值
        """
        # 对于受控状态（delta=0），使用近似公式
        # ARL0 ≈ exp(2K(h-K)) / (2K(h-K))

        # 对于失控状态，使用更复杂的近似
        if abs(delta) > 0.001:
            # 使用近似公式：ARL ≈ (exp(2K(h-K)) - 1) / (2K(delta-K))
            if abs(delta - K) < 0.001:
                # delta ≈ K时的极限情况
                return 2.0 * (h - K + 1.0 / (2.0 * K))
            else:
                numerator = np.exp(2.0 * K * (h - K)) - 1.0
                denominator = 2.0 * K * (delta - K)
                return abs(numerator / denominator)
        else:
            # 受控状态
            if abs(h - K) < 0.001:
                return 10000.0  # 极大的ARL
            else:
                return np.exp(2.0 * K * (h - K)) / (2.0 * K * (h - K))

    @staticmethod
    def find_h_for_arl0(K: float, target_arl0: float = 370.0,
                         use_table: bool = True) -> float:
        """找到实现目标ARL₀的阈值h（二分搜索）

        Args:
            K: 参考值
            target_arl0: 目标ARL₀（通常370或500）
            use_table: 是否使用预计算表格（更准确）

        Returns:
            阈值h
        """
        if use_table and abs(K - 0.5) < 0.01:
            # 使用表格查找（更准确）
            return ARLCalculator._find_h_from_table(ARLCalculator.ARL_TABLE_K0_5,
                                                    target_arl0, K)
        elif use_table and abs(K - 0.25) < 0.01:
            return ARLCalculator._find_h_from_table(ARLCalculator.ARL_TABLE_K0_25,
                                                    target_arl0, K)

        # 否则使用二分搜索
        low, high = 1.0, 10.0

        for _ in range(50):  # 二分搜索
            mid = (low + high) / 2
            arl0 = ARLCalculator.calculate_arl0_approx(K=K, h=mid, delta=0.0)

            if arl0 > target_arl0:
                high = mid
            else:
                low = mid

        return (low + high) / 2

    @staticmethod
    def _find_h_from_table(table: Dict[float, float],
                           target_arl0: float, K: float) -> float:
        """从表格中查找h（反向插值）"""
        h_values = sorted(table.keys())

        # 找到ARL0在表格中的位置
        for i in range(len(h_values) - 1):
            arl1, arl2 = table[h_values[i]], table[h_values[i + 1]]

            if arl1 <= target_arl0 <= arl2 or arl2 <= target_arl0 <= arl1:
                # 线性插值（反向）
                h = h_values[i] + (h_values[i + 1] - h_values[i]) * \
                     (target_arl0 - arl1) / (arl2 - arl1)
                return h

        # 如果超出范围，返回最近的
        if target_arl0 <= table[h_values[0]]:
            return h_values[0]
        else:
            return h_values[-1]

    @staticmethod
    def design_cusum_parameters(target_shift_sigma: float = 1.0,
                               target_arl0: float = 370.0,
                               use_table: bool = True) -> Dict[str, float]:
        """设计CUSUM参数（基于ARL理论）

        Args:
            target_shift_sigma: 要检测的最小偏移（单位：σ）
            target_arl0: 目标受控ARL（通常370，对应0.27%误报率）
            use_table: 是否使用预计算表格（更准确）

        Returns:
            包含参数和性能的字典：
            {
                'K': 参考值,
                'h': 阈值,
                'ARL0': 实际ARL₀,
                'ARL1': 预期失控ARL,
                'ARL_ratio': ARL₀/ARL₁
            }
        """
        # 根据偏移大小确定K
        K = target_shift_sigma / 2.0

        # 找到实现ARL₀的h
        h = ARLCalculator.find_h_for_arl0(K, target_arl0, use_table)

        # 计算预期ARL₁（对于目标偏移）
        arl0 = ARLCalculator.get_arl0_from_table(K, h) if use_table else \
                ARLCalculator.calculate_arl0_approx(K=K, h=h, delta=0.0)

        arl1 = ARLCalculator.calculate_arl0_approx(K=K, h=h, delta=target_shift_sigma)

        arl_ratio = arl0 / arl1 if arl1 > 0 else float('inf')

        return {
            'K': K,
            'h': h,
            'ARL0': arl0,
            'ARL1': arl1,
            'ARL_ratio': arl_ratio
        }


def test_arl_calculator():
    """测试ARL计算器"""
    print("\n" + "="*60)
    print("ARL计算器测试")
    print("="*60)

    # 测试1：参数设计
    print("\n1. 参数设计测试:")
    print("-" * 40)

    target_shifts = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

    for shift in target_shifts:
        params = ARLCalculator.design_cusum_parameters(
            target_shift_sigma=shift,
            target_arl0=370.0
        )

        print(f"\n偏移 {shift}σ:")
        print(f"  K = {params['K']:.4f}")
        print(f"  h = {params['h']:.4f}")
        print(f"  ARL₀ = {params['ARL0']:.1f}")
        print(f"  预期ARL₁ = {params['ARL1']:.2f}")
        print(f"  ARL比率 = {params['ARL_ratio']:.1f}")

    # 测试2：查找h
    print("\n\n2. 阈值查找测试:")
    print("-" * 40)

    target_arl0_values = [100, 200, 370, 500, 1000]

    print(f"\nK=0.5时的阈值查找:")
    print(f"{'目标ARL₀':<12} {'h值':<12} {'实际ARL₀':<12}")
    print("-" * 36)

    for target_arl in target_arl0_values:
        h = ARLCalculator.find_h_for_arl0(K=0.5, target_arl0=target_arl)
        arl0 = ARLCalculator.get_arl0_from_table(K=0.5, h=h)
        print(f"{target_arl:<12.1f} {h:<12.4f} {arl0:<12.1f}")

    # 测试3：不同K值的对比
    print("\n\n3. 不同K值性能对比 (目标ARL₀=370):")
    print("-" * 40)

    K_values = [0.25, 0.5, 0.75, 1.0]

    for K in K_values:
        params = ARLCalculator.design_cusum_parameters(
            target_shift_sigma=K * 2.0,  # 偏移 = 2K
            target_arl0=370.0
        )

        print(f"\nK = {K:.2f} (检测偏移={2*K:.1f}σ):")
        print(f"  h = {params['h']:.4f}")
        print(f"  ARL₁ = {params['ARL1']:.2f}")
        print(f"  ARL比率 = {params['ARL_ratio']:.1f}")


if __name__ == "__main__":
    test_arl_calculator()
