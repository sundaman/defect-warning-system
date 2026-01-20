
import sys
import os
sys.path.append(os.getcwd())
from src.core.adaptive_cusum import AdaptiveCUSUMDetector
import matplotlib.pyplot as plt

def simulate_user_scenario():
    print("Simulating User Scenario (Shift=5.5)...")
    detector = AdaptiveCUSUMDetector(
        mu0=0.01, # Non-zero to avoid std=0
        base_uph=1000,
        target_shift_sigma=5.5, # Huge shift
        target_arl0=999,
        monitoring_side='upper',
        use_standardization=True
    )
    
    # Init h
    # h = 2/5.5^2 * ln(999) = 2/30.25 * 6.9 = 0.066 * 6.9 = 0.45
    print(f"Calculated h: {detector.base_h}")
    
    s_plus_history = []
    
    # 1. Normal
    for _ in range(5):
        detector.update(0.0, 1000)
        s_plus_history.append(detector.last_calculation['S_plus'])
        
    # 2. Ramp Up (Anomaly) - mimic a hump
    # target shift 5.5 sigma. std=1.0.
    values = [1.0, 3.0, 5.0, 6.0, 5.0, 3.0, 1.0, 0.0]
    
    print("\n--- Processing Data ---")
    for v in values:
        is_alert = detector.update(v, 1000)
        s = detector.last_calculation['S_plus']
        h = detector.last_calculation['threshold']
        print(f"Val={v}, S+={s:.4f}, h={h:.4f}, Alert={is_alert}")
        s_plus_history.append(s)

if __name__ == "__main__":
    simulate_user_scenario()
