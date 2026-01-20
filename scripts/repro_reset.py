
import sys
import os
sys.path.append(os.getcwd())
from src.core.adaptive_cusum import AdaptiveCUSUMDetector

def test_cusum_reset():
    print("Testing CUSUM Reset Logic...")
    detector = AdaptiveCUSUMDetector(
        mu0=0.0005,
        base_uph=1000,
        target_shift_sigma=1.0,
        target_arl0=100,
        monitoring_side='upper',
        use_standardization=True
    )
    
    # Init h
    print(f"Initial h: {detector.base_h}")
    
    # 1. Feed normal data
    detector.update(0.0005, 1000)
    print(f"Normal: S+={detector.S_plus}, h={detector.last_calculation['threshold']}")
    
    # 2. Trigger Alert (Spike)
    print("\n--- Triggering Alert ---")
    is_alert = detector.update(0.1, 1000) # Huge spike
    print(f"Spike: S+={detector.last_calculation['S_plus']:.2f}, h={detector.last_calculation['threshold']:.2f}, Alert={is_alert}")

    # 3. Feed "Medium" data (Slightly above mean, but below trigger deviation if starting from 0)
    # mu0=0.0005. k=0.001 (approx). 
    # Let's feed 0.001. Deviation approx k. 
    # If Reset: S+ = 0 + (0.001 - 0.0005 - k) ~ 0 or small.
    # If No Reset: S+ = Huge + small ~ Huge.
    
    print("\n--- Feeding Medium Data (0.0008) ---")
    for i in range(5):
        val = 0.0008
        is_alert = detector.update(val, 1000)
        s_plus = detector.last_calculation['S_plus']
        h = detector.last_calculation['threshold']
        print(f"Step {i}: Val={val}, S+={s_plus:.4f}, h={h:.4f}, Alert={is_alert}")

if __name__ == "__main__":
    test_cusum_reset()
