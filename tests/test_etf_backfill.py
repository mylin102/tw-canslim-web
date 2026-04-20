from importlib import import_module


def test_resolve_etf_tickers_prefers_requested_subset_and_limit():
    module = import_module("update_etf_backfill")

    class StubUpdater:
        ticker_info = {"0050": {}, "00631L": {}, "2330": {}, "00878": {}}

        def is_etf_ticker(self, ticker: str) -> bool:
            return ticker in {"0050", "00631L", "00878"}

    updater = StubUpdater()

    assert module.resolve_etf_tickers(updater, "00631L,2330,0050", 0) == ["00631L", "0050"]
    assert module.resolve_etf_tickers(updater, None, 2) == ["0050", "00631L"]
