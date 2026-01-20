
import json
import os
import sys

# Assume default path based on observed structure
CONFIG_FILE = "data/storage/item_configs.json"

if not os.path.exists(CONFIG_FILE):
    # Try finding it
    print(f"File {CONFIG_FILE} not found. Searching...")
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".json") and "config" in file:
                print(f"Found: {os.path.join(root, file)}")
                
    sys.exit(1)

print(f"Reading {CONFIG_FILE}...")
with open(CONFIG_FILE, 'r') as f:
    data = json.load(f)

print(json.dumps(data, indent=2))
