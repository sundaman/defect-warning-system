import json
import os
from typing import Dict, Any

class ConfigStore:
    """
    极简的配置持久化层 (MVP版使用 JSON)
    """
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.configs: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save(self):
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.configs, f, indent=2, ensure_ascii=False)

    def set_item_config(self, item_name: str, config: Dict[str, Any]):
        if item_name not in self.configs:
            self.configs[item_name] = {}
        self.configs[item_name].update(config)
        self.save()

    def get_item_config(self, item_name: str) -> Dict[str, Any]:
        return self.configs.get(item_name, {})

    def delete_item_config(self, item_name: str):
        if item_name in self.configs:
            del self.configs[item_name]
            self.save()

    def get_all_items(self) -> Dict[str, Any]:
        # Filter out special keys
        return {k: v for k, v in self.configs.items() if not k.startswith("__")}

    def set_global_config(self, config: Dict[str, Any]):
        self.configs["__GLOBAL_CONFIG__"] = config
        self.save()

    def get_global_config(self) -> Dict[str, Any]:
        return self.configs.get("__GLOBAL_CONFIG__", {})

# --- State Persistence (SQLite) ---
from ..db.database import SessionLocal
from ..db.models import ItemState
from typing import List

def load_all_item_states() -> Dict[str, Dict]:
    """从数据库加载所有检测器的状态"""
    db = SessionLocal()
    try:
        states = db.query(ItemState).all()
        return {
            s.item_name: {
                "baseline": s.baseline,
                "std": s.std,
                "k_value": s.k_value,
                "s_plus": s.s_plus,
                "s_minus": s.s_minus,
                "last_data_timestamp": s.last_data_timestamp
            }
            for s in states
        }
    except Exception as e:
        print(f"Load states failed: {e}")
        return {}
    finally:
        db.close()

def save_item_states(states_data: List[Dict]):
    """批量保存检测器状态到数据库 (Upsert)"""
    if not states_data:
        return

    db = SessionLocal()
    try:
        # SQLite Upsert via Merge
        # SQLAlchemy merge is slow for batch, but efficient enough for 100k items if batched?
        # For 1M items, raw SQL bulk insert/update is better. 
        # But let's stick to merge for simplicity first.
        # Optimized: Delete then Insert? No, that loses history updated_at if not careful.
        # Let's use merge for now.
        
        for data in states_data:
            state_obj = ItemState(
                item_name=data["item_name"],
                baseline=data["baseline"],
                std=data["std"],
                k_value=data["k_value"],
                s_plus=data["s_plus"],
                s_minus=data["s_minus"],
                last_data_timestamp=data.get("last_data_timestamp")
            )
            db.merge(state_obj)
            
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Save states failed: {e}")
    finally:
        db.close()

def delete_item_states(item_names: List[str]):
    """批量删除检测器状态"""
    if not item_names:
        return
        
    db = SessionLocal()
    try:
        # 批量删除
        db.query(ItemState).filter(ItemState.item_name.in_(item_names)).delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Delete states failed: {e}")
    finally:
        db.close()
