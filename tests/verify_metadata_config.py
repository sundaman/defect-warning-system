
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_metadata_configuration():
    print(">>> Testing Metadata Configuration Isolation...")
    
    item_name = "ConfigTestItem"
    
    # 1. Register Specific Config for Product A
    # Product A: Strict Penalty (1.0), Base UPH 1000
    ctx_a = {"product": "ProdA", "line": "L1", "station": "S1"}
    
    # We use batch-import API to simulate UI behavior (or register API)
    # Let's use register API directly first as it's simpler? 
    # Actually register API sets config for a specific KEY if we implement it right?
    # In main.py: register_item generates key if metadata present. Yes.
    
    payload_a = {
        "item_name": item_name,
        "item_type": "parameter", 
        "mu0": 0.0005,
        "base_uph": 1000,
        "penalty_strength": 1.0,
        "meta_data": ctx_a
    }
    
    # Call internal manager/store directly is hard from script.
    # But we can assume API works if we use `requests` but server isn't running?
    # Wait, I am in the environment where I can run python scripts that import the app.
    # I should use direct import verification like before, it's faster and doesn't require starting server.
    
    from src.api.main import engine_manager, config_store
    
    # Reset for test
    if item_name in engine_manager.detectors:
        del engine_manager.detectors[item_name]
    
    # 1. Register Config A (Specific)
    key_a = engine_manager._generate_detector_key(item_name, ctx_a)
    config_store.set_item_config(key_a, {
        "mu0": 0.0005,
        "base_uph": 1000,
        "penalty_strength": 1.0,
        "item_type": "parameter"
    })
    
    # 2. Register Generic Config (Fallback)
    # Generic: Relaxed Penalty (0.3), Base UPH 500
    config_store.set_item_config(item_name, {
        "mu0": 0.0005,
        "base_uph": 500,
        "penalty_strength": 0.3,
        "item_type": "parameter"
    })
    
    # 3. Process Data for Product A
    print("   [Step 3] ingesting data for Product A...")
    from src.api.main import ingest_data, DataIngestRequest
    # Mock BackgroundTasks
    class MockBg:
        def add_task(self, *args, **kwargs): pass
        
    req_a = DataIngestRequest(
        item_name=item_name,
        item_type="parameter",
        value=1.5,
        uph=1000,
        meta_data=ctx_a
    )
    
    import asyncio
    # ingest_data is async
    try:
        asyncio.run(ingest_data(req_a, MockBg()))
    except Exception as e:
        print(f"Ingest A failed: {e}")
        
    # Verify Detector A
    det_a = engine_manager.detectors.get(key_a)
    if det_a:
        print(f"   [Check A] Detector Base UPH: {det_a.base_uph} (Expected 1000)")
        assert det_a.base_uph == 1000, f"Expected 1000, got {det_a.base_uph}"
        print("   [Pass] Product A used specific config.")
    else:
        print("   [Fail] Detector A not created!")

    # 4. Process Data for Product B (Should fall back to Generic)
    print("   [Step 4] ingesting data for Product B...")
    ctx_b = {"product": "ProdB", "line": "L1", "station": "S1"}
    req_b = DataIngestRequest(
        item_name=item_name,
        item_type="parameter",
        value=1.5,
        uph=500,
        meta_data=ctx_b
    )
    
    try:
        asyncio.run(ingest_data(req_b, MockBg()))
    except Exception as e:
        print(f"Ingest B failed: {e}")
        
    key_b = engine_manager._generate_detector_key(item_name, ctx_b)
    det_b = engine_manager.detectors.get(key_b)
    if det_b:
        print(f"   [Check B] Detector Base UPH: {det_b.base_uph} (Expected 500)")
        assert det_b.base_uph == 500, f"Expected 500, got {det_b.base_uph}"
        print("   [Pass] Product B used generic fallback config.")
    else:
        print("   [Fail] Detector B not created!")

if __name__ == "__main__":
    test_metadata_configuration()
