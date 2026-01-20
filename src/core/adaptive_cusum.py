# adaptive_cusum.py
import numpy as np
from datetime import datetime
from typing import Dict
from .baseline_updater import AdaptiveBaseline
from .k_updater import AdaptiveKUpdater


class AdaptiveCUSUMDetector:
    """自适应CUSUM检测器 - 支持FIR和EWMA优化"""

    def __init__(
            self,
            mu0,
            base_uph,
            base_h=0.007,
            min_uph_ratio=0.5,
            min_detection_ratio=0.15,
            min_k=0.001,
            penalty_strength=1.0, # 惩罚强度系数 (1.0=原算法, 0.6=温和, 0.3=宽松)
            use_standardization=True,  # 是否使用标准化残差方法（推荐）
            use_arl=True,  # 是否使用ARL理论设计参数（推荐）
            target_shift_sigma=1.0,  # 要检测的最小偏移（单位：σ）
            target_arl0=250.0,  # 目标ARL₀（控制误报率）
            item_type="yield",  # yield 或 parameter
            monitoring_side="upper",  # upper, lower, 或 both
            # ========== FIR CUSUM（P1优化）==========
            use_fir=False,  # 是否使用FIR CUSUM（P1优化）
            fir_ratio=0.004,  # FIR初始值比例（基于ARL理论，f ≈ 0.004）
            fir_duration=700,  # FIR持续时间（样本数）
            # ========== EWMA参数更新（P2优化）==========
            use_ewma=False,  # 是否使用EWMA参数更新
            ewma_lambda=0.2,  # EWMA衰减因子（新数据权重20%）
    ):
        """
        初始化自适应CUSUM检测器

        Args:
            mu0: 初始基准值
            base_uph: 基准UPH（或基准采样频率）
            base_h: 基准阈值
            item_type: 监控项类型 ("yield" 或 "parameter")
            monitoring_side: 监控方向 ("upper", "lower", "both")
            ... 其他参数保持一致
        """
        self.mu0 = mu0
        self.base_uph = base_uph
        self.base_h = base_h
        self.min_uph_ratio = min_uph_ratio
        self.min_detection_ratio = min_detection_ratio
        self.min_k = min_k
        self.penalty_strength = penalty_strength
        self.use_standardization = use_standardization
        self.use_arl = use_arl
        
        # Internal storage for properties
        self._target_shift_sigma = target_shift_sigma
        self._target_arl0 = target_arl0
        
        self.item_type = item_type
        self.monitoring_side = monitoring_side

        # 计算基于ARL理论的基础h值
        self._recalculate_h()

        # 初始化状态
        self.S_plus = 0.0
        self.S_minus = 0.0
        self.h_history = []

        # FIR相关状态
        self.use_fir = use_fir
        self.fir_ratio = fir_ratio
        self.fir_duration = fir_duration
        self.samples_since_reset = 0
        self.total_samples = 0
        self.fir_active = False

        # EWMA相关状态
        self.use_ewma = use_ewma
        self.ewma_lambda = ewma_lambda
        self.ewma_baseline = mu0

        # 初始化参数更新器
        self.baseline_updater = AdaptiveBaseline(
            window_size=700,
            update_interval=24,
            max_change_ratio=0.1,
            invalid_points_around_alert=10,
            base_uph=base_uph,
            min_detection_ratio=min_detection_ratio
        )

        self.k_updater = AdaptiveKUpdater(
            window_size=700,
            update_interval=24,
            max_change_ratio=0.1,
            invalid_points_around_alert=10,
            base_uph=base_uph,
            min_detection_ratio=min_detection_ratio
        )

    def _recalculate_h(self):
        import sys
        sys.stderr.write(f"[DEBUG-CORE] Recalculating H. Shift={self._target_shift_sigma}, ARL0={self._target_arl0}\\n")
        if self.use_arl:
            delta = self._target_shift_sigma
            if delta > 0:
                self.base_h = (2.0 / (delta ** 2)) * np.log(self._target_arl0)
            else:
                self.base_h = 11.04 # 默认标准值
                
    @property
    def target_shift_sigma(self):
        return self._target_shift_sigma
        
    @target_shift_sigma.setter
    def target_shift_sigma(self, value):
        self._target_shift_sigma = value
        self._recalculate_h()
        
    @property
    def target_arl0(self):
        return self._target_arl0
        
    @target_arl0.setter
    def target_arl0(self, value):
        self._target_arl0 = value
        self._recalculate_h()

    def update(self, x, current_uph=None, timestamp=None, line_state=None):
        """
        更新检测器状态并返回是否报警

        Args:
            x: 当前值 (defect rate)
            current_uph: 当前UPH
            timestamp: 时间戳
            line_state: 产线状态 (optional)
        """
        value = x # 内部使用 value 变量名
        
        # 更新计数器
        self.samples_since_reset += 1

        # 更新参数更新器
        current_baseline = self.baseline_updater.get_current_baseline()
        if current_baseline is None:
            current_baseline = self.mu0

        self.baseline_updater.add_data_point(
            timestamp=timestamp,
            defect_rate=value,
            is_alert=False,  # 暂时设为False，后面会更新
            current_uph=current_uph,
            current_baseline=current_baseline
        )

        self.k_updater.add_data_point(
            timestamp=timestamp,
            defect_rate=value,
            is_alert=False,  # 暂时设为False，后面会更新
            current_uph=current_uph,
            current_baseline=current_baseline
        )

        # 获取当前参数
        current_baseline = self.baseline_updater.get_current_baseline()
        if current_baseline is None:
            current_baseline = self.mu0

        if self.use_ewma:
            # EWMA更新
            self.ewma_baseline = self.ewma_lambda * value + (1 - self.ewma_lambda) * self.ewma_baseline
            current_baseline = self.ewma_baseline

        current_k = self.k_updater.get_current_k()
        if current_k is None:
            current_k = self.min_k

        # 检查是否应该检测
        uph_ratio = current_uph / self.base_uph
        if uph_ratio < self.min_detection_ratio:
            self.last_calculation = {
                "baseline": current_baseline,
                "k": current_k,
                "threshold": 0.0,
                "deviation": 0.0,
                "deviation_standardized": 0.0,
                "threshold_multiplier": 0.0,
                "std": 0.0,
                "skip_reason": "UPH太低"
            }
            return False

        # 初始化状态值记录
        deviation_standardized_plus = 0.0
        deviation_standardized_minus = 0.0

        # 计算标准差
        if self.item_type == "yield":
            std_baseline = self._calculate_std(current_baseline, self.base_uph)
            std_current = self._calculate_std(current_baseline, current_uph)
        else:
            # 对于参数类，从 K 更新器获取历史窗口的标准差
            std_base_value = self.k_updater.get_current_std()
            if std_base_value is None or std_base_value <= 0:
                std_base_value = 3.0 # 默认兜底 (从1.0改为3.0，保守策略)
            
            # 根据采样数量 (uph) 缩放标准差: sigma_env = sigma / sqrt(n)
            std_baseline = std_base_value / np.sqrt(max(1, self.base_uph))
            std_current = std_base_value / np.sqrt(max(1, current_uph))

        # 计算偏差和累积和
        # 更新计数器
        self.total_samples += 1
        
        if self.use_standardization:
            if std_baseline == 0:
                threshold_multiplier = 1.0
            else:
                threshold_multiplier = std_current / std_baseline

            if uph_ratio < self.min_uph_ratio:
                extra_penalty = (self.min_uph_ratio / uph_ratio - 1) ** 0.5
                threshold_multiplier *= (1 + extra_penalty * self.penalty_strength)

            # 标准化 CUSUM 计算
            x_standardized = (value - current_baseline) / std_current
            k_standardized = current_k / std_current
            
            if self.use_arl:
                h_standardized = self.base_h * threshold_multiplier
            else:
                h_standardized = self.base_h * threshold_multiplier / std_current
                
            h_limit = h_standardized * std_current

            # 上限累积
            if self.monitoring_side in ["upper", "both"]:
                deviation_standardized_plus = x_standardized - k_standardized
                self.S_plus = max(0, self.S_plus + deviation_standardized_plus)
            
            # 下限累积
            if self.monitoring_side in ["lower", "both"]:
                deviation_standardized_minus = (-x_standardized) - k_standardized
                self.S_minus = max(0, self.S_minus + deviation_standardized_minus)

            self.h_history.append(h_limit)
            deviation = deviation_standardized_plus * std_current # 仅用于记录
            h = h_standardized # 修复：在标准化模式下，比较阈值应为标准化阈值
        else:
            # sqrt 方法处理 (作为标准化方法的备份)
            if uph_ratio >= 1:
                threshold_multiplier = 1.0
            else:
                threshold_multiplier = np.sqrt(self.base_uph / current_uph)

            if uph_ratio < self.min_uph_ratio:
                extra_penalty = (self.min_uph_ratio / uph_ratio - 1) ** 0.5
                threshold_multiplier *= (1 + extra_penalty * self.penalty_strength)

            deviation = value - current_baseline
            h = self.base_h * threshold_multiplier

            # 双向监控适配
            if self.monitoring_side in ["upper", "both"]:
                self.S_plus = max(0, self.S_plus + (deviation - current_k))
            if self.monitoring_side in ["lower", "both"]:
                self.S_minus = max(0, self.S_minus + ((-deviation) - current_k))
            
            self.h_history.append(h)

        # 检查FIR是否应该停用
        if self.fir_active and self.samples_since_reset > self.fir_duration:
            self.fir_active = False
            # 不重置CUSUM值，让它自然累积

        # 检查是否报警 (任一一侧触发即报警)
        alert_plus = (self.monitoring_side in ["upper", "both"]) and (self.S_plus >= h)
        alert_minus = (self.monitoring_side in ["lower", "both"]) and (self.S_minus >= h)
        alert = alert_plus or alert_minus

        # 记录计算过程
        self.last_calculation = {
            "baseline": current_baseline,
            "k": current_k,
            "threshold": h,
            "deviation_plus": deviation_standardized_plus * std_current,
            "deviation_minus": deviation_standardized_minus * std_current,
            "S_plus": self.S_plus,
            "S_minus": self.S_minus,
            "std": std_current,
            "uph_ratio": uph_ratio,
            "alert_side": "upper" if alert_plus else ("lower" if alert_minus else None)
        }

        # 如果报警，更新参数更新器并重置CUSUM
        if alert:
            # 更新参数更新器的报警状态
            # 这里需要找到最近的索引并更新
            # 简化处理：不更新，因为参数更新器会自动处理

            self._reset()

        return bool(alert)

    def _reset(self):
        """报警后重置累积和"""
        if self.use_fir:
            start_val = self.base_h * self.fir_ratio
            self.S_plus = start_val if self.monitoring_side in ["upper", "both"] else 0.0
            self.S_minus = start_val if self.monitoring_side in ["lower", "both"] else 0.0
            self.samples_since_reset = 0
            self.fir_active = True
        else:
            self.S_plus = 0.0
            self.S_minus = 0.0
            self.samples_since_reset = 0
            self.fir_active = False

    def _calculate_std(self, value, size):
        """计算标准差"""
        if self.item_type == "yield":
            if value <= 0 or value >= 1: return 0.0
            return np.sqrt(value * (1 - value) / size)
        else:
            # 对于参数类，std 由外部 updater 计算并在 update 中处理 uph 缩放
            # 这里仅作为签名兼容
            return 1.0

    def get_current_status(self):
        """
        获取当前算法内部状态
        
        如果最近一次 update 触发了报警并 reset, 这里返回的是 reset 前的快照。
        """
        if self.last_calculation:
            # 使用快照数据构建状态，确保 manager 拿到的是报警时刻的值
            lc = self.last_calculation
            return {
                "baseline": lc.get("baseline", 0.0),
                "S_plus": lc.get("S_plus", 0.0),
                "S_minus": lc.get("S_minus", 0.0),
                "h_value": lc.get("threshold", 0.0),
                "k_value": lc.get("k", 0.0),
                "calculation_details": lc, # 关键：必须包含此字段
                "total_samples": self.total_samples,
                "fir_active": self.fir_active
            }
        
        # 正常返回
        return {
            "baseline": self.baseline_updater.get_current_baseline() or self.mu0,
            "S_plus": self.S_plus,
            "S_minus": self.S_minus,
            "h_value": self.base_h * (self.h_history[-1] / self.base_h if self.h_history else 1.0), # 估算
            "k_value": self.k_updater.get_current_k() or self.min_k,
            "calculation_details": self.last_calculation or {},
            "total_samples": self.total_samples,
            "fir_active": self.fir_active
        }

        return {
            "baseline": status["baseline"],
            # 优先从 current status 取 std, 如果没有则尝试从 updater 获取
            "std": details.get("std", 0.0), 
            "k_value": status["k_value"],
            "s_plus": status["S_plus"],
            "s_minus": status["S_minus"]
        }

    def set_state(self, state: Dict):
        """从持久化恢复状态"""
        if not state:
            return
        
        self.S_plus = state.get("s_plus", 0.0)
        self.S_minus = state.get("s_minus", 0.0)
        
        # 简单恢复基准值 (更新 mu0 和 EWMA)
        if "baseline" in state:
            restored_base = state["baseline"]
            self.mu0 = restored_base
            self.ewma_baseline = restored_base
            # 注意: AdaptiveBaseline 内部状态比较复杂(窗口历史)，这里仅作为冷启动的初始值
            # 随着新数据进来会重新适应
            
        # 记录日志 (Optional)
        # print(f"Restored state for detector: S+={self.S_plus}")
