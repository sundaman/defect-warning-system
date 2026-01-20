
import sys
import os
import asyncio
sys.path.append(os.getcwd())
from src.api.main import batch_import_items, BatchImportRequest
from src.utils.persistence import ConfigStore

async def test_import():
    print("Testing batch import...")
    # Mock request
    req = BatchImportRequest(items=["TEST_SNAPSHOT_FIX_01"])
    
    # We need to ensure global_config is loaded in main.py scope?
    # main.py runs at module level to init global_config.
    # But batch_import_items uses 'global_config' from module scope.
    
    # Run import
    batch_import_items(req)
    
    # Check config store
    store = ConfigStore("data/storage/item_configs.json")
    cfg = store.get_item_config("TEST_SNAPSHOT_FIX_01")
    print(f"Config for TEST_SNAPSHOT_FIX_01: {cfg}")
    
    if "target_shift_sigma" in cfg:
        print("SUCCESS: target_shift_sigma is baked in.")
    else:
        print("FAILURE: target_shift_sigma is MISSING.")

if __name__ == "__main__":
    # We can't await directly in main block easily without creating loop
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_import())
