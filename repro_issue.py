import logging
from export_canslim import CanslimEngine

logging.basicConfig(level=logging.INFO)

def test_single_stock():
    engine = CanslimEngine()
    # Mock some things to avoid full run
    engine.ticker_info = {"2330": {"name": "TSMC", "suffix": ".TW"}}
    
    # We want to see if inst_cache exists and works
    print(f"inst_cache exists: {'inst_cache' in engine.__dict__}")
    
    # Try to access it
    try:
        val = engine.inst_cache.get("2330")
        print(f"inst_cache.get('2330') returned: {val}")
    except AttributeError as e:
        print(f"Caught expected AttributeError: {e}")
    except Exception as e:
        print(f"Caught unexpected Exception: {e}")

if __name__ == "__main__":
    test_single_stock()
