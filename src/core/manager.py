import collections
import time
import datetime
from typing import Dict, List, Optional, Any
from .adaptive_cusum import AdaptiveCUSUMDetector
from ..db.database import SessionLocal
from ..db.models import DetectionRecord
from ..utils.persistence import load_all_item_states, save_item_states

class DetectionEngineManager:
    """
    管理多个检测项目的引擎管理器
    - 负责维护检测项实例
    - 负责维护最近30次历史轨迹 (History Trajectory)
    - 负责报警抑制 (Cooldown Policy) 逻辑
    """
    def __init__(self, global_config: Dict[str, Any]):
        self.global_config = global_config
        self.detectors: Dict[str, AdaptiveCUSUMDetector] = {}
        # 缓存最近30周期的历史数据
        # 结构: {item_name: deque([status1, status2, ...], maxlen=30)}
        self.history_cache: Dict[str, collections.deque] = {}
        # 缓存最近的报警推送记录，用于抑制重复报警 (实际上在 history_cache 中记录了 push_executed)
        self.alert_history: Dict[str, float] = {}
        
        # 缓存的初始状态 (用于延迟加载)
        self.initial_states = {}
        
        # 报警抑制规则：将从项目配置中读取
        # self.cooldown_periods = global_config.get("cooldown_periods", 6)
        self.enable_cooldown = global_config.get("enable_cooldown", True)

    def get_or_create_detector(self, item_name: str, item_type: str, mu0: float, base_uph: float, monitoring_side: Optional[str] = None, **kwargs) -> AdaptiveCUSUMDetector:
        if item_name not in self.detectors:
            # 优先级: item_config > global_config > default rule
            if monitoring_side is None:
                monitoring_side = self.global_config.get("monitoring_side")
            
            # Default rule if still nothing
            if not monitoring_side:
                monitoring_side = "both" if item_type == "parameter" else "upper"
            
            detector = AdaptiveCUSUMDetector(
                mu0=mu0,
                base_uph=base_uph,
                target_shift_sigma=self.global_config.get("target_shift_sigma", 1.0),
                target_arl0=self.global_config.get("target_arl0", 250.0),
                item_type=item_type,
                monitoring_side=monitoring_side,
                use_standardization=True,
                use_arl=True,
                penalty_strength=kwargs.get("penalty_strength", 1.0)
            )
            
            # 尝试恢复状态
            if item_name in self.initial_states:
                detector.set_state(self.initial_states[item_name])
                del self.initial_states[item_name]

            self.detectors[item_name] = detector
            self.history_cache[item_name] = collections.deque(maxlen=30)
        return self.detectors[item_name]

    def remove_detector(self, item_name: str):
        if item_name in self.detectors:
            del self.detectors[item_name]
        if item_name in self.history_cache:
            del self.history_cache[item_name]

    def load_all_states(self):
        """服务启动时加载所有状态"""
        count = 0
        try:
            self.initial_states = load_all_item_states()
            count = len(self.initial_states)
        except Exception as e:
            print(f"Failed to load states: {e}")
        return count

    def save_all_states(self):
        """保存当前内存中所有检测器的状态"""
        states_to_save = []
        for name, detector in self.detectors.items():
            state = detector.get_state()
            state["item_name"] = name
            state["last_data_timestamp"] = datetime.datetime.now()
            states_to_save.append(state)
        
        if states_to_save:
            save_item_states(states_to_save)
            return len(states_to_save)
        return 0

    def _generate_detector_key(self, item_name: str, metadata: Dict) -> str:
        """
        生成唯一检测键值
        Format: Product::Line::Station::ItemName
        如果 Metadata 缺失，则降级为只使用 ItemName (兼容旧行为，但建议都带上)
        """
        if not metadata:
            return item_name
            
        product = str(metadata.get("product", "UnknownProduct")).lower()
        line = str(metadata.get("line", "UnknownLine")).lower()
        station = str(metadata.get("station", "UnknownStation")).lower()
        
        # 使用双冒号作为分隔符，避免与常规名称冲突
        return f"{product}::{line}::{station}::{item_name}"

    def process_data(self, item_name: str, item_type: str, value: float, uph: int, timestamp: Any, metadata: Dict, item_config: Dict = None):
        """
        处理单条接入数据
        """
        # 统一转换时间戳为 datetime 对象
        if isinstance(timestamp, str):
            try:
                # 尝试解析 ISO 格式
                # 处理 Z 后缀 (python 3.9 fromisoformat 不完全支持 Z，需替换为 +00:00)
                ts_str = timestamp.replace('Z', '+00:00')
                current_time = datetime.datetime.fromisoformat(ts_str)
            except ValueError:
                # 尝试常见格式
                try:
                    current_time = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S")
                except:
                    current_time = datetime.datetime.now()
        elif isinstance(timestamp, datetime.datetime):
            current_time = timestamp
        else:
            current_time = datetime.datetime.now()

        # 生成唯一键值 (Composite Key)
        unique_key = self._generate_detector_key(item_name, metadata)

        # 优先使用传入的 item_config
        if item_config:
            mu0 = item_config.get("mu0", 0.0005)
            base_uph = item_config.get("base_uph", 500)
            penalty_strength = item_config.get("penalty_strength", 1.0)
            monitoring_side = item_config.get("monitoring_side")
        else:
            # Fallback (Legacy) - 注意：这里仍然使用原始 item_name 查找配置，
            # 因为配置通常是针对"检测项"本身的，而不是针对"特定产线的检测项"。
            # 如果未来需要针对特定产线配置不同参数，这里也需要修改。
            # 目前假设同一 item 在不同产线配置相同。
            mu0 = self.global_config.get(f"mu0_{item_name}", 0.0005)
            base_uph = self.global_config.get(f"base_uph_{item_name}", 500)
            penalty_strength = self.global_config.get(f"penalty_strength_{item_name}", 1.0)
            monitoring_side = None

        # 使用 unique_key 获取/创建检测器
        detector = self.get_or_create_detector(unique_key, item_type, mu0=mu0, base_uph=base_uph, monitoring_side=monitoring_side, penalty_strength=penalty_strength)
        
        # 调用算法更新
        is_alert = detector.update(
            x=value,
            current_uph=uph,
            timestamp=current_time,
            line_state="normal"
        )
        
        # 获取当前计算详情
        status = detector.get_current_status()
        status['timestamp'] = timestamp
        status['value'] = value
        status['uph'] = uph
        status['metadata'] = metadata
        
        # 检测是否需要推送 (报警抑制逻辑) - 使用 unique_key
        should_push = False
        if is_alert:
            should_push = self._check_should_push(unique_key)
            status['push_executed'] = should_push
        else:
            status['push_executed'] = False

        # 存入轨迹缓存 - 使用 unique_key
        self.history_cache[unique_key].append(status)
        
        # --- 数据持久化 (SQLite) ---
        try:
            db = SessionLocal()
            record = DetectionRecord(
                item_name=item_name,       # 数据库中保持原始 Item Name 方便查询
                item_type=item_type,
                station=metadata.get("station"),
                product=metadata.get("product"),
                line=metadata.get("line"),
                timestamp=current_time,
                value=value,
                uph=uph,
                baseline=status['baseline'],
                std=status['calculation_details'].get('std', 0.0),
                k_value=status['k_value'],
                h_value=status['h_value'],
                s_plus=status['S_plus'],
                s_minus=status['S_minus'],
                is_alert=is_alert,
                alert_side=status['calculation_details'].get('alert_side')
            )
            db.add(record)
            db.commit()
            db.close()
        except Exception as e:
            print(f"[ERROR] Failed to save record: {e}")
                
        return {
            "item_name": item_name,
            "unique_key": unique_key, # 返回唯一键值供调试
            "alert": is_alert,
            "should_push": should_push,
            "alert_side": status['calculation_details'].get('alert_side'),
            "current_status": status,
            "history": list(self.history_cache[unique_key])
        }

    def _check_should_push(self, item_key: str) -> bool:
        """
        报警抑制逻辑：如果在最近 N 个周期内已经执行过推送，则不再重复推送。
        注意：item_key 现在的含义是 Unique Key
        """
        if not self.enable_cooldown:
            return True
            
        history_list = list(self.history_cache[item_key])
        if not history_list:
            return True
            
        # 查找最近 N 个周期 (动态配置)
        # 配置仍然是基于原始 Item Name 的 (假定配置共享)
        # 从 key 中提取原始 Item Name
        original_item_name = item_key.split("::")[-1] if "::" in item_key else item_key
        
        cooldown_periods = self.global_config.get(f"cooldown_periods_{original_item_name}", 6)
        check_range = min(len(history_list), cooldown_periods)
        
        for i in range(1, check_range + 1):
            past_status = history_list[-i]
            if past_status.get('push_executed'):
                return False 
                
        return True
