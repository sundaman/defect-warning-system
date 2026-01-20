import os
import sys
import datetime
import random
import uuid

# Add src to path
sys.path.append(os.getcwd())

from src.db.database import SessionLocal, engine, Base
from src.db.models import DetectionRecord

def benchmark():
    # Setup clean DB
    db_path = "data/storage/benchmark.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    # Use a separate engine for benchmark
    from sqlalchemy import create_engine
    bench_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bench_engine)
    Session = sessionmaker(bind=bench_engine)
    session = Session()
    
    # Generate 10,000 records
    batch_size = 10000
    print(f"[*] Inserting {batch_size} records...")
    
    items = []
    base_time = datetime.datetime.now()
    
    for i in range(batch_size):
        record = DetectionRecord(
            item_name=f"ITEM_{i % 1000}", # Simulate 1000 unique items
            item_type="parameter",
            station="STATION_01",
            product="PRODUCT_A",
            line="LINE_01",
            timestamp=base_time + datetime.timedelta(seconds=i),
            value=random.random(),
            uph=500,
            baseline=0.5,
            std=0.1,
            k_value=0.005,
            h_value=0.015,
            s_plus=0.0,
            s_minus=0.0,
            is_alert=False,
            alert_side=None
        )
        items.append(record)
        
    session.add_all(items)
    session.commit()
    session.close()
    
    # Check size
    size_bytes = os.path.getsize(db_path)
    size_kb = size_bytes / 1024
    bytes_per_row = size_bytes / batch_size
    
    print(f"[*] Total Size: {size_kb:.2f} KB")
    print(f"[*] Bytes per Row: {bytes_per_row:.2f} bytes")
    
    # Cleanup
    os.remove(db_path)

if __name__ == "__main__":
    from sqlalchemy.orm import sessionmaker
    benchmark()
