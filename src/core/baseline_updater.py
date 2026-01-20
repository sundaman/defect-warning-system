import numpy as np
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class BaselineUpdate:
    """记录基础不良率更新的数据类"""
    timestamp: datetime
    old_value: float
    new_value: float
    is_limited: bool  # 是否触发最大步长限制
    valid_points: int  # 参与计算的有效点数
    window_points: int  # 窗口总点数

class AdaptiveBaseline:
    def __init__(
        self,
        window_size: int = 700,  # 滑动窗口大小
        update_interval: int = 24,  # 24小时更新一次
        max_change_ratio: float = 0.1,  # 最大变化步长（百分比）
        invalid_points_around_alert: int = 10,  # 异常点前后的无效点数
        base_uph: int = 500,  # 基准UPH
        min_detection_ratio: float = 0.1  # 最小检测UPH比例
    ):
        """初始化自适应基础不良率计算器"""
        self.window_size = window_size
        self.update_interval = update_interval
        self.max_change_ratio = max_change_ratio
        self.invalid_points_around_alert = invalid_points_around_alert
        self.base_uph = base_uph
        self.min_detection_ratio = min_detection_ratio
        
        # 初始化状态
        self.current_baseline = None  # 当前基础不良率
        self.last_update_time = None  # 上次更新时间
        self.update_history: List[BaselineUpdate] = []  # 更新历史
        self.data_buffer = []  # 数据缓冲区（完整数据）
        self.alert_points = set()  # 异常点集合
        self.sliding_buffer = []  # 滑动窗口缓冲区（用于计算基础不良率）
        self.sliding_alerts = set()  # 滑动窗口中的异常点集合
        self.low_uph_points = set()  # 极低UPH点集合
    
    def add_data_point(self, timestamp: datetime, defect_rate: float, is_alert: bool, 
                      current_uph: float, current_baseline: float) -> None:
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
        if len(self.sliding_buffer) > self.window_size:
            self.sliding_buffer.pop(0)
            # 更新滑动窗口中的异常点索引
            self.sliding_alerts = {i-1 for i in self.sliding_alerts if i > 0}
        
        # 检查是否需要更新基础不良率
        if self._should_update(timestamp):
            self._update_baseline()
    
    def _should_update(self, current_time: datetime) -> bool:
        """检查是否应该更新基础不良率"""
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
        
        # 添加异常点及其前后的点
        for alert_idx in self.sliding_alerts:
            start = max(0, alert_idx - self.invalid_points_around_alert)
            end = min(len(self.sliding_buffer), 
                     alert_idx + self.invalid_points_around_alert + 1)
            invalid_indices.update(range(start, end))
        
        return invalid_indices
    
    def _update_baseline(self) -> None:
        """更新基础不良率"""
        if len(self.sliding_buffer) < self.window_size:
            return
        
        # 获取有效数据点
        invalid_indices = self._get_invalid_indices()
        valid_rates = [
            rate for idx, (_, rate, _) in enumerate(self.sliding_buffer)
            if idx not in invalid_indices
        ]
        
        if not valid_rates:  # 如果没有有效数据点
            return
        
        # 计算新的基础不良率
        new_baseline = np.mean(valid_rates)
        
        # 如果是首次更新
        if self.current_baseline is None:
            self.current_baseline = new_baseline
            is_limited = False
        else:
            # 检查变化是否超过最大步长
            max_change = self.current_baseline * self.max_change_ratio
            change = new_baseline - self.current_baseline
            is_limited = abs(change) > max_change
            
            if is_limited:
                # 按最大步长更新
                sign = 1 if change > 0 else -1
                new_baseline = self.current_baseline + sign * max_change
        
        # 记录更新
        update = BaselineUpdate(
            timestamp=self.sliding_buffer[-1][0],
            old_value=self.current_baseline if self.current_baseline is not None else new_baseline,
            new_value=new_baseline,
            is_limited=is_limited,
            valid_points=len(valid_rates),
            window_points=len(self.sliding_buffer)
        )
        self.update_history.append(update)
        
        # 更新状态
        self.current_baseline = new_baseline
        self.last_update_time = self.sliding_buffer[-1][0]
    
    def get_current_baseline(self) -> Optional[float]:
        """获取当前基础不良率"""
        return self.current_baseline

    def update_alert_status(self, index: int, is_alert: bool) -> None:
        """更新指定索引的异常状态"""
        if is_alert:
            self.alert_points.add(index)
        else:
            self.alert_points.discard(index) 