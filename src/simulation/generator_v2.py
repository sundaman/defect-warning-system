import random
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

@dataclass
class Metadata:
    """元数据模型"""
    item_name: str
    station: str
    product: str
    line: str

@dataclass
class Config:
    """数据生成配置参数"""
    # 基础参数
    total_hours: int = 1000  # Default 1000 hours
    base_defect_rate: float = 0.0005
    base_defect_rate_std: float = 0.0001
    min_defect_rate: float = 0.0
    zero_defect_probability: float = 0.1
    
    # 生产状态参数
    line_state_thresholds: Dict = field(default_factory=lambda: {
        "IDLE": 150,
        "RAMP_UP": 600
    })
    
    # UPH场景参数
    uph_scenarios: List[Dict] = field(default_factory=lambda: [
        {"uph_range": (480, 520), "duration": 200},   # Normal
        {"uph_range": (1, 90), "duration": 100},      # Low
        {"uph_range": (240, 260), "duration": 100},   # Medium
        {"uph_range": (480, 520), "duration": 600}    # Normal
    ])
    
    # 异常事件参数
    anomaly_count: int = 5
    event_duration: Tuple[int, int] = (5, 20)
    defect_rate_range: Tuple[float, float] = (0.004, 0.08)
    peak_time_range: Tuple[float, float] = (0.2, 0.8)
    peak_ratio_range: Tuple[float, float] = (1.2, 2.0)
    min_event_interval: int = 24
    
    # 随机波动参数
    normal_noise_range: Tuple[float, float] = (0.8, 1.2)
    anomaly_noise_range: Tuple[float, float] = (0.8, 1.2)
    uph_noise_range: Tuple[float, float] = (0.9, 1.1)

@dataclass
class AnomalyEvent:
    start_hour: int
    duration: int
    base_defect_rate: float
    peak_time: float
    peak_ratio: float
    target_uph: int
    event_id: int

def generate_base_data(config: Config, metadata: Metadata, start_time: datetime) -> List[Dict]:
    """生成基础正常数据"""
    data = []
    current_hour = 0
    
    for scenario in config.uph_scenarios:
        uph_min, uph_max = scenario["uph_range"]
        for _ in range(scenario["duration"]):
            current_uph = random.randint(uph_min, uph_max)
            input_qty = max(1, int(current_uph * random.uniform(*config.uph_noise_range)))
            
            if random.random() < config.zero_defect_probability:
                defect_count = 0
            else:
                current_base_rate = max(
                    config.min_defect_rate,
                    random.gauss(config.base_defect_rate, config.base_defect_rate_std)
                )
                lambda_defect = input_qty * current_base_rate * random.uniform(*config.normal_noise_range)
                defect_count = int(np.ceil(np.random.poisson(lambda_defect)))
            
            defect_rate = defect_count / input_qty if input_qty > 0 else 0
            
            if current_uph < config.line_state_thresholds["IDLE"]:
                line_state = "IDLE"
            elif current_uph > config.line_state_thresholds["RAMP_UP"]:
                line_state = "RAMP_UP"
            else:
                line_state = "NORMAL"
            
            timestamp = (start_time + timedelta(hours=current_hour)).isoformat()
            
            row = {
                "timestamp": timestamp,
                "item_name": metadata.item_name,
                "station": metadata.station,
                "product": metadata.product,
                "line": metadata.line,
                "defect_count": defect_count,
                "input_qty": input_qty,
                "value": round(defect_rate, 6), # Standardize to 'value' for system compatibility
                "current_uph": current_uph,
                "line_state": line_state,
                "alarm_type": "False",
                "event_id": 0
            }
            data.append(row)
            current_hour += 1
    
    return data

def calculate_event_defect_rate(event: AnomalyEvent, hour_index: int) -> float:
    relative_time = hour_index / event.duration
    gaussian = np.exp(-((relative_time - event.peak_time) ** 2) / (2 * 0.2 ** 2))
    current_ratio = 1 + (event.peak_ratio - 1) * gaussian
    noise_ratio = random.uniform(0.8, 1.2)
    return event.base_defect_rate * current_ratio * noise_ratio

def find_matching_uph_periods(data: List[Dict], event: AnomalyEvent, max_uph_diff: int = 20) -> List[Tuple[int, int]]:
    matching_periods = []
    current_period_start = None
    
    for i, row in enumerate(data):
        if abs(row["current_uph"] - event.target_uph) <= max_uph_diff:
            if current_period_start is None:
                current_period_start = i
        else:
            if current_period_start is not None and i - current_period_start >= event.duration:
                matching_periods.append((current_period_start, i))
            current_period_start = None
            
    if current_period_start is not None and len(data) - current_period_start >= event.duration:
        matching_periods.append((current_period_start, len(data)))
    
    return matching_periods

def insert_anomaly_events(data: List[Dict], events: List[AnomalyEvent]) -> List[Dict]:
    used_hours = set()
    
    for event in events:
        matching_periods = find_matching_uph_periods(data, event)
        if not matching_periods:
            continue
            
        random.shuffle(matching_periods)
        valid_start_found = False
        
        for period_start, period_end in matching_periods:
            possible_starts = list(range(period_start, period_end - event.duration + 1))
            random.shuffle(possible_starts)
            
            for start_hour in possible_starts:
                if not any(h in used_hours for h in range(start_hour, start_hour + event.duration)):
                    event.start_hour = start_hour
                    used_hours.update(range(start_hour, start_hour + event.duration))
                    valid_start_found = True
                    break
            if valid_start_found:
                break
                
    events = [e for e in events if e.start_hour > 0]
    events.sort(key=lambda x: x.start_hour)
    
    for event in events:
        for hour_offset in range(event.duration):
            hour = event.start_hour + hour_offset
            row = data[hour]
            input_qty = row["input_qty"]
            
            current_defect_rate = calculate_event_defect_rate(event, hour_offset)
            defect_count = int(np.ceil(input_qty * current_defect_rate))
            
            data[hour].update({
                "defect_count": defect_count,
                "value": round(defect_count / input_qty, 6),
                "alarm_type": "True",
                "event_id": event.event_id
            })
            
    return data

def generate_scenario_data(config: Config, metadata: Metadata) -> List[Dict]:
    """生成特定场景的仿真数据"""
    start_time = datetime.now() - timedelta(hours=config.total_hours)
    
    # 1. Generate Base Data
    data = generate_base_data(config, metadata, start_time)
    
    # 2. Generate Events
    events = []
    # Simplified event generation logic for scenario testing
    # Just generate 'anomaly_count' events distributed across data
    
    if config.anomaly_count > 0:
        # Determine accessible UPH ranges from data
        uph_values = [d['current_uph'] for d in data]
        min_uph, max_uph = min(uph_values), max(uph_values)
        
        for i in range(config.anomaly_count):
            target_uph = random.randint(min_uph, max_uph)
            events.append(AnomalyEvent(
                start_hour=0,
                duration=random.randint(*config.event_duration),
                base_defect_rate=random.uniform(*config.defect_rate_range),
                peak_time=random.uniform(*config.peak_time_range),
                peak_ratio=random.uniform(*config.peak_ratio_range),
                target_uph=target_uph,
                event_id=i+1
            ))
            
        data = insert_anomaly_events(data, events)
        
    return data
