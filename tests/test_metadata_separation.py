
import unittest
from datetime import datetime
from src.core.manager import DetectionEngineManager

class TestMetadataSeparation(unittest.TestCase):
    def setUp(self):
        self.config = {
            "mu0": 0.0005,
            "base_uph": 500,
            "enable_cooldown": False # Disable cooldown to simplify testing
        }
        self.manager = DetectionEngineManager(self.config)

    def test_key_generation(self):
        """Test that keys are generated correctly based on metadata"""
        item_name = "VoltageCheck"
        
        # Case 1: Full Metadata
        meta1 = {"product": "PhoneX", "line": "L1", "station": "S1"}
        key1 = self.manager._generate_detector_key(item_name, meta1)
        self.assertEqual(key1, "PhoneX::L1::S1::VoltageCheck")
        
        # Case 2: Partial Metadata (defaults used)
        meta2 = {"product": "PhoneY"}
        key2 = self.manager._generate_detector_key(item_name, meta2)
        # Assuming missing keys default to "Unknown..."
        self.assertEqual(key2, "PhoneY::UnknownLine::UnknownStation::VoltageCheck")
        
        # Case 3: No Metadata (fallback to item_name)
        key3 = self.manager._generate_detector_key(item_name, {})
        self.assertEqual(key3, "VoltageCheck")

    def test_data_isolation(self):
        """Test that same item name with different metadata creates different detectors"""
        item_name = "GapTest"
        
        # Product A
        meta_a = {"product": "ProdA", "line": "L1", "station": "S1"}
        self.manager.process_data(item_name, "parameter", 1.0, 500, datetime.now(), meta_a)
        
        # Product B
        meta_b = {"product": "ProdB", "line": "L1", "station": "S1"}
        self.manager.process_data(item_name, "parameter", 1.1, 500, datetime.now(), meta_b)
        
        # Verify detectors dict keys
        keys = list(self.manager.detectors.keys())
        expected_key_a = "ProdA::L1::S1::GapTest"
        expected_key_b = "ProdB::L1::S1::GapTest"
        
        self.assertIn(expected_key_a, keys)
        self.assertIn(expected_key_b, keys)
        self.assertEqual(len(keys), 2)
        
        # Verify independence
        # Access detectors directly
        det_a = self.manager.detectors[expected_key_a]
        det_b = self.manager.detectors[expected_key_b]
        
        self.assertNotEqual(id(det_a), id(det_b))

    def test_backward_compatibility(self):
        """Test that requests without metadata use the simple item name as key"""
        item_name = "LegacyItem"
        self.manager.process_data(item_name, "parameter", 0.5, 500, datetime.now(), {})
        
        self.assertIn("LegacyItem", self.manager.detectors)

if __name__ == '__main__':
    unittest.main()
