"""
Compress data.json to data.json.gz for faster loading.
Run after export_canslim.py generates data.json.
"""

import gzip
import json
import os
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "docs")
DATA_JSON = os.path.join(OUTPUT_DIR, "data.json")
DATA_GZ = os.path.join(OUTPUT_DIR, "data.json.gz")


def compress_json():
    """Compress data.json to data.json.gz"""
    if not os.path.exists(DATA_JSON):
        print(f"❌ {DATA_JSON} not found")
        return False
    
    # Read JSON
    with open(DATA_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"✅ Loaded {len(data.get('stocks', {}))} stocks")
    print(f"   Original size: {os.path.getsize(DATA_JSON) / 1024:.1f} KB")
    
    # Compress
    json_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
    compressed = gzip.compress(json_bytes, compresslevel=9)
    
    with open(DATA_GZ, 'wb') as f:
        f.write(compressed)
    
    print(f"   Compressed: {len(compressed) / 1024:.1f} KB")
    print(f"   Saved: {(1 - len(compressed) / len(json_bytes)) * 100:.1f}%")
    print(f"✅ Saved to {DATA_GZ}")
    
    return True


if __name__ == "__main__":
    compress_json()
