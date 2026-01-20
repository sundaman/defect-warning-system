from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
import os
import sys

# 添加 src 到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.db.models import DetectionRecord, Base

# 数据库路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "storage", "defect_warning.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

print(f"Checking database at: {DB_PATH}")

if not os.path.exists(DB_PATH):
    print("❌ Database file does NOT exist!")
    sys.exit(1)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

try:
    # 查询所有 Item Name
    items = session.query(
        DetectionRecord.item_name, 
        func.count(DetectionRecord.id),
        func.min(DetectionRecord.timestamp),
        func.max(DetectionRecord.timestamp)
    ).group_by(DetectionRecord.item_name).all()
    
    if not items:
        print("⚠️ Database exists but table 'detection_records' is empty or no records found.")
    else:
        print("\n✅ Found the following items in DB:")
        print(f"{'Item Name':<25} | {'Count':<8} | {'Min Time':<20} | {'Max Time':<20}")
        print("-" * 80)
        for name, count, min_t, max_t in items:
            print(f"{name:<25} | {count:<8} | {str(min_t):<20} | {str(max_t):<20}")

except Exception as e:
    print(f"❌ Error querying database: {e}")
finally:
    session.close()
