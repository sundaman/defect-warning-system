import numpy as np
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional, Dict
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.utils.arl_calculator import ARLCalculator

@dataclass
class KValueUpdate:
    """记录K值更新的数据类"""
    timestamp: datetime
    old_value: float
    new_value: float
    is_limited: bool  # 是否触发最大步长限制
    valid_points: int  # 参与计算的有效点数
    window_points: int  # 窗口总点数
    std: float  # 标准差

class AdaptiveKUpdater:
    def __init__(
        self,
        window_size: int = 700,  # 与基础不良率更新器共用相同的窗口大小
        update_interval: int = 24,  # 共用相同的更新周期
        max_change_ratio: float = 0.1,  # 共用相同的最大变化步长
        invalid_points_around_alert: int = 10,  # 共用相同的无效点设置
        base_uph: int = 500,  # 共用相同的基准UPH
        min_detection_ratio: float = 0.1,  # 共用相同的最小检测比例
        min_k: float = 0.001,  # 最小K值
        use_arl: bool = True,  # 是否使用ARL理论
        target_shift_sigma: float = 1.0,  # 要检测的最小偏移（单位：σ）
        target_arl0: float = 370.0  # 目标ARL₀
    ):
        # 继承基础不良率更新器的参数
        self.window_size = window_size
        self.update_interval = update_interval
        self.max_change_ratio = max_change_ratio
        self.invalid_points_around_alert = invalid_points_around_alert
        self.base_uph = base_uph
        self.min_detection_ratio = min_detection_ratio
        self.min_k = min_k
        self.use_arl = use_arl
        self.target_shift_sigma = target_shift_sigma
        self.target_arl0 = target_arl0

        # 基于ARL理论设计初始参数
        if self.use_arl:
            self.target_shift_sigma = target_shift_sigma
            self.target_arl0 = target_arl0

            # ARL参数需要后续用数据的标准差来转换
            # 初始化使用传统方法
            self.current_k = 0.005
            self.arl_k_in_sigma_units = None  # 将在第一次更新时计算
        else:
            self.current_k = 0.005

        # 初始化状态
        self.last_update_time = None
        self.update_history = []
        self.data_buffer = []
        self.alert_points = set()
        self.sliding_buffer = []
        self.sliding_alerts = set()
        self.low_uph_points = set()
        self.last_update_time = None
        self.update_history = []
        self.data_buffer = []
        self.alert_points = set()
        self.sliding_buffer = []
        self.sliding_alerts = set()
        self.low_uph_points = set()

    def add_data_point(self, 
                      timestamp: datetime, 
                      defect_rate: float, 
                      is_alert: bool, 
                      current_uph: float,
                      current_baseline: float) -> None:
        """添加新的数据点"""
        # 记录完整数据
        self.data_buffer.append((timestamp, defect_rate, current_uph))
        current_idx = len(self.data_buffer) - 1
        
        if is_alert:
            self.alert_points.add(current_idx)
        
        # 检查是否为极低UPH点
        if current_uph < self.base_uph * self.min_detection_ratio:
            self.low_uph_points.add(current_idx)
        
        # 更新滑动窗口
        self.sliding_buffer.append((timestamp, defect_rate, current_uph))
        sliding_idx = len(self.sliding_buffer) - 1
        
        if is_alert:
            self.sliding_alerts.add(sliding_idx)
        
        # 如果滑动窗口超过大小，移除最早的数据
        while len(self.sliding_buffer) > self.window_size:
            self.sliding_buffer.pop(0)
            # 更新滑动窗口中的异常点索引
            self.sliding_alerts = {i-1 for i in self.sliding_alerts if i > 0}
            # 移除已经超出窗口的异常点
            self.sliding_alerts = {i for i in self.sliding_alerts if i >= 0}
        
        # 检查是否需要更新K值
        if self._should_update(timestamp):
            self._update_k_value(current_baseline)

    def _calculate_k(self, valid_rates: List[float], current_baseline: float) -> float:
        """计算新的K值
        支持两种方法：
        1. ARL理论方法（推荐）
        2. 传统方法（4倍标准差）
        """
        if not valid_rates:
            return self.current_k if self.current_k is not None else 0.005

        rates = np.array(valid_rates)
        std = float(np.std(rates))

        if self.use_arl:
            std_current = std
            k_sigma = self.target_shift_sigma / 2.0
            k = k_sigma * std_current
        else:
            k = 4.0 * std

        k = max(k, self.min_k)
        return k

    def _calculate_k_arl(self, valid_rates: List[float], current_baseline: float) -> float:
        """基于ARL理论计算K值"""
        if all(rate == 0 for rate in valid_rates):
            return self.min_k

        rates = np.array(valid_rates)
        std = float(np.std(rates))

        if std == 0:
            return self.target_shift_sigma / 4.0

        k_arl = self.target_shift_sigma / 2.0
        k = max(k_arl, self.min_k)

        return k

    def _calculate_k_traditional(self, valid_rates: List[float]) -> float:
        """传统方法：4倍标准差"""
        if all(rate == 0 for rate in valid_rates):
            return 0.001

        rates = np.array(valid_rates)
        std = float(np.std(rates))
        k = 4 * std
        k = max(k, self.min_k)

        return k

    def _update_k_value(self, current_baseline: float) -> None:
        """更新K值"""
        if len(self.sliding_buffer) < self.window_size:
            return
            
        # 获取有效数据点
        invalid_indices = self._get_invalid_indices()
        valid_rates = [
            rate for idx, (_, rate, _) in enumerate(self.sliding_buffer)
            if idx not in invalid_indices
        ]
        
        if not valid_rates:
            return
            
        # 计算新的K值
        new_k = self._calculate_k(valid_rates, current_baseline)
        
        # 如果是首次更新
        if self.current_k is None:
            self.current_k = new_k
            is_limited = False
        else:
            # 检查变化是否超过最大步长
            max_change = self.current_k * self.max_change_ratio
            change = new_k - self.current_k
            is_limited = abs(change) > max_change
            
            if is_limited:
                # 按最大步长更新
                sign = 1 if change > 0 else -1
                new_k = self.current_k + sign * max_change
        
        # 确保K值不小于最小值
        new_k = max(new_k, self.min_k)
        
        # 记录更新
        update = KValueUpdate(
            timestamp=self.sliding_buffer[-1][0],
            old_value=self.current_k if self.current_k is not None else float(new_k),
            new_value=float(new_k),
            is_limited=is_limited,
            valid_points=len(valid_rates),
            window_points=len(self.sliding_buffer),
            std=float(np.std(np.array(valid_rates)))
        )
        self.update_history.append(update)
        
        # 更新状态
        self.current_k = new_k
        self.last_update_time = self.sliding_buffer[-1][0]

    def _should_update(self, current_time: datetime) -> bool:
        """检查是否应该更新K值"""
        if self.last_update_time is None:
            return len(self.sliding_buffer) >= self.window_size
        
        hours_since_last_update = (current_time - self.last_update_time).total_seconds() / 3600
        return hours_since_last_update >= self.update_interval

    def _get_invalid_indices(self) -> set:
        """获取所有无效数据点的索引"""
        invalid_indices = set()
        
        # 获取滑动窗口中的极低UPH点
        for i, (_, _, uph) in enumerate(self.sliding_buffer):
            if uph < self.base_uph * self.min_detection_ratio:
                invalid_indices.add(i)
                # 同时标记前后的点
                for j in range(max(0, i - self.invalid_points_around_alert),
                             min(len(self.sliding_buffer), i + self.invalid_points_around_alert + 1)):
                    invalid_indices.add(j)
        
        # 添加异常点及其前后的点
        for alert_idx in self.sliding_alerts:
            # 标记异常点前后的点
            for i in range(max(0, alert_idx - self.invalid_points_around_alert),
                         min(len(self.sliding_buffer), alert_idx + self.invalid_points_around_alert + 1)):
                invalid_indices.add(i)
        
        return invalid_indices

    def get_current_k(self) -> Optional[float]:
        """获取当前K值"""
        return self.current_k

    def get_current_std(self) -> Optional[float]:
        """获取最近一次更新时计算的标准差"""
        if self.update_history:
            return self.update_history[-1].std
        return None

    def get_state(self) -> Dict:
        """获取当前状态"""
        return {
            "current_k": self.current_k,
            "std": self.get_current_std(),
            "last_update_time": self.last_update_time
        }

    def set_state(self, state: Dict):
        """恢复状态"""
        if state.get("current_k") is not None:
            self.current_k = state["current_k"]
        
        # 如果有保存的 Std，我们需要构造一个假的 update_history 记录
        # 这样 get_current_std() 就能返回正确的值
        if state.get("std") is not None:
             dummy_update = KValueUpdate(
                timestamp=state.get("last_data_timestamp") or datetime.datetime.now(),
                old_value=self.current_k,
                new_value=self.current_k,
                is_limited=False,
                valid_points=0,
                window_points=0,
                std=state["std"]
             )
             self.update_history.append(dummy_update)
