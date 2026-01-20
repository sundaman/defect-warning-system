from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from typing import Dict, Optional, List, Any
import datetime
import uuid
import logging
import os
import asyncio

from ..core.manager import DetectionEngineManager
from ..utils.persistence import ConfigStore, load_all_item_states, save_item_states, delete_item_states
from ..db.database import init_db, get_db, SessionLocal
from ..db.models import DetectionRecord
from sqlalchemy.orm import Session
from fastapi import Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DefectWarningAPI")

app = FastAPI(title="Industrial Defect Warning System", version="1.0.0")

# 初始化数据库
@app.on_event("startup")
def on_startup():
    init_db()

# 初始化持久化存储
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
storage_path = os.path.join(BASE_DIR, "data", "storage", "item_configs.json")
config_store = ConfigStore(storage_path)

# 全局配置 (默认值)
global_config = {
    "target_shift_sigma": 1.0,
    "target_arl0": 250.0,
    "cooldown_periods": 6,
    "enable_cooldown": True,
    "monitoring_side": "upper" 
}
# 尝试加载持久化的全局配置
persisted_global = config_store.get_global_config()
if persisted_global:
    global_config.update(persisted_global)

# 合并存储项到引擎配置中 (简单实现)
combined_config = global_config.copy()
combined_config.update(config_store.configs)

engine_manager = DetectionEngineManager(combined_config)

# --- 数据模型 ---

class DataIngestRequest(BaseModel):
    item_name: str
    item_type: str = Field(..., description="yield or parameter")
    value: float
    uph: int
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    meta_data: Dict[str, Any] = {}

class ItemRegisterRequest(BaseModel):
    item_name: str
    item_type: str
    mu0: float
    base_uph: int
    mu0: float
    base_uph: int
    penalty_strength: float = 1.0 # 默认强惩罚
    cooldown_periods: int = 6     # 默认 6 周期
    cooldown_periods: int = 6     # 默认 6 周期
    meta_data: Optional[Dict] = {}

class AlertPushDetail(BaseModel):
    alert_id: str
    item_name: str
    alert_time: str
    severity: str = "CRITICAL"
    algorithm_config: Dict
    current_status: Dict
    history_30_periods: Dict

# --- 模拟报警推送服务 ---
async def push_alert_to_external(detail: AlertPushDetail):
    logger.info(f"🚀 [PUSH ALERT] Item: {detail.item_name}, Time: {detail.alert_time}")
    # TODO: 调用微信/前端 Webhook
    pass

# --- API 端点 ---

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.now().isoformat()}

@app.post("/api/v1/data/ingest")
async def ingest_data(request: DataIngestRequest, background_tasks: BackgroundTasks):
    """
    接收实时监测数据，返回检测结果
    """
    import sys
    sys.stderr.write(f">>> ENTERING ingest_data. ManagerID={id(engine_manager)}\n")
    sys.stderr.flush()
    
    sys.stderr.flush()
    
    # Generate unique key for detection
    # Ideally should use manager's method, but accessible via engine_manager
    unique_key = engine_manager._generate_detector_key(request.item_name, request.meta_data)

    # 1. Try Specific Config
    item_cfg = config_store.get_item_config(unique_key)
    if not item_cfg:
        # 2. Try Generic Config (Item Name only)
        item_cfg = config_store.get_item_config(request.item_name)
    
    if not item_cfg:
        # 3. Use Global Defaults (Implicitly handled by passing None or defaults)
        # But we want to persist it or use it. Manager handles defaults if config is empty.
        # But here we might want to auto-register strictly for the ItemName (Generic) or UniqueKey?
        # Current logic: auto-register Generic Item Name if completely new?
        # Let's auto-register the Unique Key if it's a new context?
        # OR simply fallback to defaults without saving to avoid polluting configDB with every transient key.
        # Decision: Use defaults without saving transient config efficiently.
        item_cfg = {} 
    
    # 动态传递配置
    mu0 = item_cfg.get("mu0", 0.0005)
    base_uph = item_cfg.get("base_uph", 500)

    try:
        # 重写 manager.py 使其支持动态传递配置
        result = engine_manager.process_data(
            item_name=request.item_name,
            item_type=request.item_type,
            value=request.value,
            uph=request.uph,
            timestamp=request.timestamp,
            metadata=request.meta_data,
            item_config=item_cfg  # Pass the loaded config
        )
        
        if result["should_push"]:
            # 转出 30 周期历史
            history_data = result["history"]
            trajectory = {
                "timestamps": [s['timestamp'] for s in history_data],
                "values": [s['value'] for s in history_data],
                "baselines": [s['baseline'] for s in history_data],
                "k_values": [s['k_value'] for s in history_data],
                "cusum_plus": [s['S_plus'] for s in history_data],
                "cusum_minus": [s['S_minus'] for s in history_data],
                "threshold_h": [s['h_value'] for s in history_data]
            }
            
            alert_detail = AlertPushDetail(
                alert_id=str(uuid.uuid4()),
                item_name=request.item_name,
                alert_time=request.timestamp,
                algorithm_config=global_config,
                current_status={
                    "value": request.value,
                    "baseline": result["current_status"]["baseline"],
                    "k_value": result["current_status"]["k_value"],
                    "S_plus": result["current_status"]["S_plus"],
                    "S_minus": result["current_status"]["S_minus"],
                    "threshold_h": result["current_status"]["h_value"],
                    "alert_side": result["alert_side"]
                },
                history_30_periods=trajectory
            )
            background_tasks.add_task(push_alert_to_external, alert_detail)
            
        return {"status": "success", "alert": result["alert"], "push": result["should_push"]}
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/items/register")
async def register_item(request: ItemRegisterRequest):
    """运维端：注册/维护检测项目"""
    config_store.set_item_config(request.item_name, {
        "mu0": request.mu0,
        "base_uph": request.base_uph,
        "penalty_strength": request.penalty_strength,
        "item_type": request.item_type,
        "meta_data": request.meta_data
    })
    
    # Determine key
    key = request.item_name
    if request.meta_data:
         key = engine_manager._generate_detector_key(request.item_name, request.meta_data)
         # Also save under unique key
         config_store.set_item_config(key, {
            "mu0": request.mu0,
            "base_uph": request.base_uph,
            "penalty_strength": request.penalty_strength,
            "item_type": request.item_type,
            "meta_data": request.meta_data
        })
        
    # 同步更新引擎中的全局配置缓存 (Only for Generic Item Name to keep legacy compat?)
    # If key is specific, we don't update global_config["mu0_ItemName"] because that's for generic fallback.
    # But wait, manager.process_data looks up mu0_ItemName as fallback.
    # So if we register a specific item, we should NOT update the generic fallback unless requested.
    # Update: register_item usually implies generic unless specified.
    
    if key == request.item_name:
        engine_manager.global_config[f"mu0_{request.item_name}"] = request.mu0
        engine_manager.global_config[f"base_uph_{request.item_name}"] = request.base_uph
        engine_manager.global_config[f"penalty_strength_{request.item_name}"] = request.penalty_strength
        engine_manager.global_config[f"cooldown_periods_{request.item_name}"] = request.cooldown_periods
    return {"message": f"Item {request.item_name} registered successfully"}

@app.get("/api/v1/options")
def get_options(
    item_name: Optional[str] = Query(None),
    station: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    line: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    获取筛选菜单的动态选项 (支持联动过滤)
    """
    try:
        # Base query for filtering
        base_query = db.query(DetectionRecord)
        
        if item_name:
            base_query = base_query.filter(DetectionRecord.item_name == item_name)
        if station:
            base_query = base_query.filter(DetectionRecord.station == station)
        if product:
             base_query = base_query.filter(DetectionRecord.product == product)
        if line:
             base_query = base_query.filter(DetectionRecord.line == line)
             
        # Extract distinct values from the FILTERED set for each field
        # Note: optimizing this might require separate queries if dataset is huge, 
        # but for now iterating distinct on the filtered result is fine.
        # Actually proper SQL optimization: 
        # To get available stations GIVEN product=P, we query distinct station where product=P.
        
        # Helper to get distinct list based on current filters (excluding self to allow changing selection?)
        # Logic: Linked dropdowns usually narrow down. If I selected Product A, Station list should only show Stations for Product A.
        # If I also select Station S1, Line list should only show Lines for (Product A AND Station S1).
        
        # However, a common pattern is: 
        # The options for field X should be filtered by all OTHER Selected fields.
        # But efficiently:
        
        # Let's clone base_query for each dimension, applying all filters EXCEPT the dimension itself?
        # Or just apply all current filters to everything? 
        # If I selected Product A, and I want to change Product, I should still see List of All Products.
        # So Options for X should depend on (All Filters - Filter X).
        
        # Debug logging to see actual params
        print(f"DEBUG OPTIONS REQ: item={item_name}, st={station}, prod={product}, line={line}")

        def get_distinct(target_field_name, current_filter_val):
            # Map string name to column
            col_map = {
                "item_name": DetectionRecord.item_name,
                "station": DetectionRecord.station,
                "product": DetectionRecord.product,
                "line": DetectionRecord.line
            }
            target_col = col_map[target_field_name]
            
            q = db.query(target_col).distinct()
            
            # Apply other filters (Skip if we are querying the field itself)
            # Logic: If I am querying available 'products', I should NOT restrict by the currently selected 'product' 
            # (unless I want to force re-selection, but usually we want to see siblings).
            # But I MUST restrict by selected 'station', 'line', etc.
            
            if target_field_name != "item_name" and item_name: 
                q = q.filter(DetectionRecord.item_name == item_name)
            
            if target_field_name != "station" and station: 
                q = q.filter(DetectionRecord.station == station)
                
            if target_field_name != "product" and product: 
                q = q.filter(DetectionRecord.product == product)
                
            if target_field_name != "line" and line: 
                q = q.filter(DetectionRecord.line == line)
            
            result = [r[0] for r in q.all() if r[0]]
            print(f"DEBUG: Field {target_field_name} -> {len(result)} options")
            return sorted(result)

        return {
            "stations": get_distinct("station", station),
            "products": get_distinct("product", product),
            "lines": get_distinct("line", line),
            # Item Name is special: searching it is primary. 
            # If we want to filter item names by station, we can.
            "items": get_distinct("item_name", item_name)
        }
    except Exception as e:
        print(f"Error fetching options: {e}")
        return {"stations": [], "products": [], "lines": [], "items": []}

class ItemConfigUpdate(BaseModel):
    mu0: Optional[float] = None
    target_shift_sigma: Optional[float] = None
    target_arl0: Optional[float] = None
    cooldown_periods: Optional[int] = None
    monitoring_side: Optional[str] = None # upper, lower, both
    base_uph: Optional[float] = None # 基准产能
    penalty_strength: Optional[float] = None # 惩罚强度 (1.0=Strict, 0.6=Moderate, 0.3=Relaxed)

@app.get("/api/v1/configs")
def get_all_configs():
    """获取所有项目的配置信息"""
    all_configs = config_store.get_all_items()
    # 同时返回全局默认配置作为参考
    return {
        "global_defaults": global_config,
        "item_configs": all_configs
    }

# --- Global Config API ---

class GlobalConfigUpdate(BaseModel):
    target_shift_sigma: Optional[float] = None
    target_arl0: Optional[float] = None
    cooldown_periods: Optional[int] = None
    enable_cooldown: Optional[bool] = None
    mu0: Optional[float] = None
    monitoring_side: Optional[str] = None
    base_uph: Optional[float] = None
    penalty_strength: Optional[float] = None

@app.put("/api/v1/configs/global")
def update_global_config(config: GlobalConfigUpdate):
    """更新全局默认参数 (Default Policy for New Items)"""
    import sys
    sys.stderr.write(f">>> ENTERING update_global_config. Default Policy Updated.\\n")
    sys.stderr.flush()
    
    update_data = {k: v for k, v in config.dict().items() if v is not None}
    
    if not update_data:
        return {"message": "No changes provided"}
        
    # 1. 更新内存中的 global_config (作为 Default)
    global_config.update(update_data)
    
    # 2. 持久化
    config_store.set_global_config(global_config)
    
    # 3. Manager 更新 Default
    engine_manager.global_config.update(update_data) 
    # Cooldown 仍然是全局生效的 (如果开启 Cooldown)
    if "enable_cooldown" in update_data:
        engine_manager.enable_cooldown = update_data["enable_cooldown"]

    # 注意：不再主动遍历 engine_manager.detectors 进行更新。
    # 现有 Item 保持原样，只有新 Item 会使用新的 Default。
             
    return {
        "message": "Default policy updated (Applied to NEW items only)", 
        "current_global": global_config
    }

@app.put("/api/v1/configs/{item_name}")
def update_item_config(item_name: str, config: ItemConfigUpdate):
    """更新指定项目的配置"""
    # 转换为 dict 并过滤 None 值
    update_data = {k: v for k, v in config.dict().items() if v is not None}
    
    if not update_data:
        return {"message": "No changes provided"}

    # 1. 持久化存储
    config_store.set_item_config(item_name, update_data)
    
    # 2. 实时更新运行中的 detector 实例 (如果有)
    if item_name in engine_manager.detectors:
        detector = engine_manager.detectors[item_name]
        if "target_shift_sigma" in update_data:
            detector.target_shift_sigma = update_data["target_shift_sigma"]
        if "target_arl0" in update_data:
            detector.target_arl0 = update_data["target_arl0"]
        if "mu0" in update_data:
            detector.mu0 = update_data["mu0"]
        if "monitoring_side" in update_data:
            detector.monitoring_side = update_data["monitoring_side"]
        if "base_uph" in update_data:
            detector.base_uph = update_data["base_uph"]
        if "penalty_strength" in update_data:
            detector.penalty_strength = update_data["penalty_strength"]
            
    return {"message": f"Config for {item_name} updated successfully", "updated": update_data}

@app.delete("/api/v1/configs/{item_name}")
def delete_item_config(item_name: str):
    """删除指定项目的配置及运行实例"""
    # 1. 从内存和持久化中删除
    config_store.delete_item_config(item_name)
    
    # 2. 从 Manager 中移除
    engine_manager.remove_detector(item_name)
    
    # 3. 清除数据库中的历史状态
    delete_item_states([item_name])
    
    return {"message": f"Item {item_name} deleted successfully"}

class BatchDeleteRequest(BaseModel):
    items: List[str]

@app.post("/api/v1/configs/batch-delete")
def batch_delete_items(request: BatchDeleteRequest):
    """批量删除项目"""
    count = 0
    errors = []
    
    # 批量清理状态 (Pre-emptive)
    if request.items:
        delete_item_states(request.items)
    
    for item_name in request.items:
        try:
            # 1. 持久化删除
            config_store.delete_item_config(item_name)
            # 2. 内存移除
            engine_manager.remove_detector(item_name)
            count += 1
        except Exception as e:
            errors.append(f"{item_name}: {str(e)}")
            
    return {
        "message": f"Successfully deleted {count} items.", 
        "errors": errors,
        "deleted_count": count
    }

# --- Item Import API ---

class BatchImportRequest(BaseModel):
    items: List[str]
    config: Optional[ItemConfigUpdate] = None  # Allow overriding defaults during import
    meta_data: Optional[Dict] = {} # Context for all items in this batch


@app.post("/api/v1/items/batch-import")
def batch_import_items(request: BatchImportRequest):
    """批量导入项目，支持指定初始配置"""
    count = 0
    overrides = {}
    if request.config:
        overrides = {k: v for k, v in request.config.dict().items() if v is not None}

    for item_name in request.items:
        if not item_name or not item_name.strip():
            continue
            
        item_name = item_name.strip()
        # merge overrides with defaults (logic handled by creating config with explicit values)
        # We start with Current Defaults (global_config) as base? No, set_item_config handles persistence.
        # But we want to 'bake' the current values into the item config.
        
        # Base config structure
        # Base config structure
        new_config = {
            "mu0": overrides.get("mu0", global_config.get("mu0", 0.0005)), 
            "base_uph": overrides.get("base_uph", global_config.get("base_uph", 500)),
            "penalty_strength": overrides.get("penalty_strength", 1.0),
            "item_type": "parameter" # default assumption
        }
        
        # Merge specific algorithm params if they differ from default?
        # Ideally we save them explicitly if the user provided them in "config".
        if "target_shift_sigma" in overrides:
            new_config["target_shift_sigma"] = overrides["target_shift_sigma"]
        else:
            # Bake in the current global default so it doesn't change later if global changes
            new_config["target_shift_sigma"] = global_config.get("target_shift_sigma", 1.0)
            
        if "target_arl0" in overrides:
            new_config["target_arl0"] = overrides["target_arl0"]
        else:
            new_config["target_arl0"] = global_config.get("target_arl0", 250.0)
            
        if "cooldown_periods" in overrides:
             new_config["cooldown_periods"] = overrides["cooldown_periods"]
        else:
             new_config["cooldown_periods"] = global_config.get("cooldown_periods", 10)
             
        if "monitoring_side" in overrides:
            new_config["monitoring_side"] = overrides["monitoring_side"]
        elif "monitoring_side" in global_config:
            new_config["monitoring_side"] = global_config["monitoring_side"]

        key = item_name
        if request.meta_data:
             # If batch import has metadata context (e.g. specific product), use composite key
             key = engine_manager._generate_detector_key(item_name, request.meta_data)
             print(f"DEBUG: Generated Key: {key} for item: {item_name} with meta: {request.meta_data}")
             # Also store metadata in config for reference
             new_config["meta_data"] = request.meta_data
        else:
             print(f"DEBUG: No metadata provided for item: {item_name}")

        config_store.set_item_config(key, new_config)
        print(f"DEBUG: Saved config for key: {key}")
        count += 1
        
    return {"message": f"Successfully imported {count} items with custom configuration.", "total_requested": len(request.items)}

@app.get("/api/v1/history")
def get_history(
    item_name: Optional[str] = Query(None, description="检测项名称"), # 改为可选，或者支持组合筛选
    station: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    line: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None, description="例如 2023-01-01T00:00:00"),
    end_time: Optional[str] = Query(None),
    limit: int = 200,
    db: Session = Depends(get_db)
):
    """查询历史检测数据 (支持多维筛选)"""
    query = db.query(DetectionRecord)
    
    if item_name:
        query = query.filter(DetectionRecord.item_name == item_name)
    if station:
        query = query.filter(DetectionRecord.station == station)
    if product:
        query = query.filter(DetectionRecord.product == product)
    if line:
        query = query.filter(DetectionRecord.line == line)
    
    if start_time:
        try:
            st = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            query = query.filter(DetectionRecord.timestamp >= st)
        except:
            pass
            
    if end_time:
        try:
            et = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            query = query.filter(DetectionRecord.timestamp <= et)
        except:
            pass
            
    records = query.order_by(DetectionRecord.timestamp.asc()).limit(limit).all()
    return [r.to_dict() for r in records]

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """返回运维看板页面"""
    index_path = os.path.join(BASE_DIR, "src", "web", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Dashboard is under construction 🚧</h1>"

@app.get("/api/v1/monitor/status")
def get_system_status():
    """实时监控接口 (供前端看板展示接入状态)"""
    stats = {}
    for name, deque in engine_manager.history_cache.items():
        if deque:
            last = deque[-1]
            stats[name] = {
                "last_val": last["value"],
                "last_time": last["timestamp"],
                "alert": last.get("alert", False),
                "last_baseline": last["baseline"]
            }
    return {"active_items_count": len(stats), "items": stats}

# --- Background Tasks ---

@app.on_event("startup")
async def startup_event():
    # 0. 确保数据库表存在
    init_db()

    # 1. 尝试从数据库加载算法状态
    try:
        count = engine_manager.load_all_states()
        logger.info(f"Startup: Loaded {count} item states from persistence.")
        
        # 1.1 Pre-warm detectors from ConfigStore to ensure Monitor List is populated
        loaded_configs = config_store.get_all_items()
        logger.info(f"Startup: Pre-loading {len(loaded_configs)} detectors from config...")
        for key, cfg in loaded_configs.items():
             try:
                 engine_manager.get_or_create_detector(
                    item_name=key, # unique_key
                    item_type=cfg.get("item_type", "parameter"),
                    mu0=cfg.get("mu0", 0.001), 
                    base_uph=cfg.get("base_uph", 500),
                    monitoring_side=cfg.get("monitoring_side"),
                    penalty_strength=cfg.get("penalty_strength", 1.0)
                )
             except Exception as inner_e:
                 logger.error(f"Failed to init detector {key}: {inner_e}")
                 
        logger.info(f"Startup: {len(engine_manager.detectors)} detectors active.")
        
    except Exception as e:
        logger.error(f"Startup load failed: {e}")

    # 2. 启动后台任务
    asyncio.create_task(periodic_cleanup())
    asyncio.create_task(periodic_save_state())

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutdown: Saving all algorithm states...")
    try:
        count = engine_manager.save_all_states()
        logger.info(f"Shutdown: Saved {count} item states.")
    except Exception as e:
        logger.error(f"Shutdown save failed: {e}")

async def periodic_cleanup():
    """定期清理 30 天前的旧数据"""
    while True:
        try:
            # 每天执行一次
            # logger.info("Executing periodic data cleanup...")
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=30)
            
            db = SessionLocal()
            try:
                # 使用原生 SQL 或 ORM 删除
                num_deleted = db.query(DetectionRecord).filter(DetectionRecord.timestamp < cutoff_date).delete()
                db.commit()
                if num_deleted > 0:
                     logger.info(f"Cleanup complete. Deleted {num_deleted} old records.")
            except Exception as e:
                logger.error(f"Cleanup failed: {str(e)}")
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Cleanup task wrapper error: {str(e)}")
            
        # 等待 24 小时 (86400 seconds)
        await asyncio.sleep(86400)

async def periodic_save_state():
    """定期保存算法状态 (每日)"""
    while True:
        try:
            # 初始等待 1 小时，防止启动时立刻执行
            await asyncio.sleep(3600) 
            
            count = engine_manager.save_all_states()
            logger.info(f"Periodic Save: Saved {count} item states.")
            
            # 之后每 24 小时保存一次
            await asyncio.sleep(86400)
        except Exception as e:
             logger.error(f"Periodic Save failed: {e}")
             await asyncio.sleep(3600) # retry later
