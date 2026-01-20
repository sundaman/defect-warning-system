import sys
import os
import json
import random
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.simulation.generator_v2 import generate_scenario_data, Config, Metadata
from src.core.manager import DetectionEngineManager
from src.utils.persistence import ConfigStore
from src.db.database import engine, Base, DB_DIR
import os

# Initialize ConfigStore
config_path = os.path.join(DB_DIR, "item_configs.json")
config_store = ConfigStore(config_path)

# Initialize Engine
manager = DetectionEngineManager(global_config={
    "enable_cooldown": True,
    "cooldown_periods": 5
})

def run_scenarios():
    # 0. Clean Slate (Reset DB)
    print("Resetting Database...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # 0.1 Clean States (Optional: delete json files if we want perfection, but Drop DB + Save States will overwrite)
    # Note: If we don't delete item_states.json, manager might load old states if we used load_all_states (we didn't here).
    # manager starts fresh.
    
    scenarios = [
        # Scenario 1: Stable High Volume
        {
            "name": "Scenario 1: Stable High Volume",
            "metadata": Metadata(item_name="MIC_TEST", station="Audio", product="Phone15", line="L1"),
            "config": Config(
                total_hours=200, 
                base_defect_rate=0.0001, 
                anomaly_count=0, 
                uph_scenarios=[{"uph_range": (500, 550), "duration": 200}]
            ),
            "item_config": {"mu0": 0.0001, "base_uph": 500, "monitoring_side": "upper", "target_shift_sigma": 3.0}
        },
        # Scenario 2: Drifting Process
        {
            "name": "Scenario 2: Drifting Process",
            "metadata": Metadata(item_name="GAP_TEST", station="Screen", product="Watch9", line="L2"),
            "config": Config(
                total_hours=200,
                base_defect_rate=0.002,
                anomaly_count=5, 
                defect_rate_range=(0.005, 0.01), 
                event_duration=(5, 10)
            ),
            "item_config": {"mu0": 0.002, "base_uph": 500, "monitoring_side": "upper", "target_shift_sigma": 1.5}
        },
        # Scenario 3: Ramp Up Instability
        {
            "name": "Scenario 3: Ramp Up Instability",
            "metadata": Metadata(item_name="SOLDER_FAIL", station="SMT", product="NewPad", line="L3"),
            "config": Config(
                total_hours=300,
                base_defect_rate=0.001,
                zero_defect_probability=0.3,
                uph_scenarios=[{"uph_range": (50, 100), "duration": 300}], 
                anomaly_count=3,
                defect_rate_range=(0.02, 0.05)
            ),
            "item_config": {"mu0": 0.001, "base_uph": 100, "monitoring_side": "upper", "target_shift_sigma": 2.0}
        },
        # Scenario 4: Sudden Battery Spike
        {
            "name": "Scenario 4: Sudden Battery Spike",
            "metadata": Metadata(item_name="VOLT_TEST", station="Battery", product="TWS", line="L1"),
            "config": Config(
                total_hours=200,
                base_defect_rate=0.0005,
                anomaly_count=1,
                event_duration=(2, 4), 
                defect_rate_range=(0.10, 0.20)
            ),
            "item_config": {"mu0": 0.0005, "base_uph": 500, "monitoring_side": "upper", "target_shift_sigma": 3.0}
        },
        # Scenario 5: Intermittent Fan Fail
        {
            "name": "Scenario 5: Intermittent Fan Fail",
            "metadata": Metadata(item_name="FAN_SPEED", station="Chassis", product="Server", line="L2"),
            "config": Config(
                total_hours=400,
                base_defect_rate=0.0002,
                anomaly_count=10, 
                event_duration=(1, 2), 
                defect_rate_range=(0.01, 0.03)
            ),
            "item_config": {"mu0": 0.0002, "base_uph": 500, "monitoring_side": "upper", "target_shift_sigma": 2.5}
        }
    ]

    print("Starting Simulation for 5 Scenarios...")
    
    for sc in scenarios:
        meta = sc["metadata"]
        cfg = sc["config"]
        item_cfg = sc["item_config"]
        
        print(f"\nProcessing {sc['name']}...")
        
        # 1. Register Config (So UI shows it in list and backend knows about it)
        # Use composite key for precision
        key = manager._generate_detector_key(meta.item_name, {
            "station": meta.station, 
            "product": meta.product, 
            "line": meta.line
        })
        
        store_cfg = item_cfg.copy()
        store_cfg["item_type"] = "parameter"
        store_cfg["meta_data"] = {
            "station": meta.station, 
            "product": meta.product, 
            "line": meta.line
        }
        
        config_store.set_item_config(key, store_cfg)
        # Also map simple item_name for backward compat/dashboard grouping if needed
        config_store.set_item_config(meta.item_name, store_cfg)
        
        # Update Manager Global Hack for this loop
        manager.global_config["target_shift_sigma"] = item_cfg.get("target_shift_sigma", 1.0)
        
        # 2. Generate Data
        sim_data = generate_scenario_data(cfg, meta)
        
        # 3. Inject
        count = 0
        for r in sim_data:
            manager.process_data(
                item_name=r["item_name"],
                item_type="measurement",
                value=r["value"], 
                uph=r["current_uph"],
                timestamp=r["timestamp"],
                metadata={
                    "station": r["station"],
                    "product": r["product"],
                    "line": r["line"]
                },
                item_config=item_cfg
            )
            count += 1
            if count % 100 == 0:
                print(f"  Processed {count}/{len(sim_data)} records...", end='\r')
        
        print(f"  -> Injected {count} records. Configured with sigma={manager.global_config['target_shift_sigma']}")

    # 4. Save Runtime States (So CUSUM continues from here)
    saved_count = manager.save_all_states()
    print(f"\n✅ Simulation Complete. DB Reset. {saved_count} items state saved. Configs registered.")

if __name__ == "__main__":
    run_scenarios()
