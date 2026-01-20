from unittest.mock import MagicMock
# Mocking the logic directly to verify flow
class MockQuery:
    def __init__(self, key):
        self.key = key
        self.filters = []
    def distinct(self): return self
    def filter(self, condition):
        self.filters.append(str(condition))
        return self
    def all(self):
        return [(f"val_{self.key}",)]

def test_logic(target_field_name, filters):
    # filters dict: {item_name, station, product, line}
    print(f"\n--- Testing Target: {target_field_name} with filters: {filters} ---")
    
    q_mock = MockQuery(target_field_name)
    
    # Logic from main.py
    item_name = filters.get("item_name")
    station = filters.get("station")
    product = filters.get("product")
    line = filters.get("line")
    
    if target_field_name != "item_name" and item_name: 
        q_mock.filter(f"DetectionRecord.item_name == {item_name}")
    
    if target_field_name != "station" and station: 
        q_mock.filter(f"DetectionRecord.station == {station}")
        
    if target_field_name != "product" and product: 
        q_mock.filter(f"DetectionRecord.product == {product}")
        
    if target_field_name != "line" and line: 
        q_mock.filter(f"DetectionRecord.line == {line}")
        
    print("Applied Filters:", q_mock.filters)

# Scenario 1: Select Product="P1", query Stations
test_logic("station", {"product": "P1", "station": None, "line": None, "item_name": None})
# Expect: Filter by Product=P1

# Scenario 2: Select Product="P1", query Products (should see all)
test_logic("product", {"product": "P1", "station": None, "line": None, "item_name": None})
# Expect: NO filter by Product (allow switching)

# Scenario 3: Select Product="P1", Station="S1", query Lines
test_logic("line", {"product": "P1", "station": "S1", "line": None, "item_name": None})
# Expect: Filter by Product=P1 AND Station=S1
