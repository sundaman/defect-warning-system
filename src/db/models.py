from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

class DetectionRecord(Base):
    __tablename__ = "detection_records"

    id = Column(Integer, primary_key=True, index=True)
    item_name = Column(String, index=True)
    item_type = Column(String)
    timestamp = Column(DateTime, index=True)
    
    # 维度信息 (用于筛选)
    station = Column(String, nullable=True, index=True)
    product = Column(String, nullable=True, index=True)
    line = Column(String, nullable=True, index=True)
    
    # 原始数据
    value = Column(Float)
    uph = Column(Integer)
    
    # 算法状态
    baseline = Column(Float) # mu
    std = Column(Float)      # sigma (当前使用的)
    k_value = Column(Float)
    h_value = Column(Float)  # 动态阈值
    
    # CUSUM 状态
    s_plus = Column(Float)
    s_minus = Column(Float)
    
    # 结果
    is_alert = Column(Boolean)
    alert_side = Column(String, nullable=True) # upper/lower

    def to_dict(self):
        return {
            "id": self.id,
            "item_name": self.item_name,
            "station": self.station,
            "product": self.product,
            "line": self.line,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "value": self.value,
            "uph": self.uph,
            "baseline": self.baseline,
            "std": self.std,
            "k_value": self.k_value,
            "h_value": self.h_value,
            "s_plus": self.s_plus,
            "s_minus": self.s_minus,
            "is_alert": self.is_alert,
            "alert_side": self.alert_side
        }

class ItemState(Base):
    """
    存储算法中间状态 (Checkpoint)
    用于服务重启后恢复"记忆"
    """
    __tablename__ = "item_states"

    item_name = Column(String, primary_key=True, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # 核心状态参数
    baseline = Column(Float)
    std = Column(Float)
    k_value = Column(Float)
    s_plus = Column(Float)
    s_minus = Column(Float)
    
    # 辅助信息 (如最后一次更新时间戳，用于判断新鲜度)
    last_data_timestamp = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "item_name": self.item_name,
            "baseline": self.baseline,
            "std": self.std,
            "k_value": self.k_value,
            "s_plus": self.s_plus,
            "s_minus": self.s_minus,
            "updated_at": self.updated_at,
            "last_data_timestamp": self.last_data_timestamp
        }
