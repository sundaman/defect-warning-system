from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./data/storage/defect_warning.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def check_data():
    session = SessionLocal()
    try:
        # Check MIC_TEST
        print("--- MIC_TEST Records (Last 5) ---")
        result = session.execute(text("SELECT timestamp, value, s_plus, s_minus, h_value, is_alert FROM detection_records WHERE item_name='MIC_TEST' ORDER BY timestamp DESC LIMIT 5"))
        rows = result.fetchall()
        if not rows:
            print("No records found for MIC_TEST")
        for row in rows:
            print(row)
            
        # Check Total Count
        count = session.execute(text("SELECT count(*) FROM detection_records")).scalar()
        print(f"\nTotal Records in DB: {count}")
        
        # Check Alerts
        print("\n--- Any Alerts in DB? (Last 5) ---")
        alerts = session.execute(text("SELECT item_name, timestamp, s_plus, is_alert FROM detection_records WHERE is_alert=1 ORDER BY timestamp DESC LIMIT 5"))
        for a in alerts.fetchall():
            print(a)
            
    finally:
        session.close()

if __name__ == "__main__":
    check_data()
