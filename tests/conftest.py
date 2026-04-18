import gzip
import json
from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def publish_paths(tmp_path: Path) -> dict[str, Path]:
    docs_dir = tmp_path / "docs"
    backup_dir = tmp_path / "backups" / "last_good"
    docs_dir.mkdir(parents=True)
    backup_dir.mkdir(parents=True)
    return {
        "root": tmp_path,
        "docs": docs_dir,
        "backup": backup_dir,
        "lock": docs_dir / ".publish.lock",
    }


@pytest.fixture
def sample_stock_entry():
    def factory(
        symbol: str = "2330",
        *,
        schema_version: str = "1.0",
        mansfield_rs: float = 88.1,
        grid_strategy: dict | None = None,
    ) -> dict:
        return {
            "schema_version": schema_version,
            "symbol": symbol,
            "name": f"Stock {symbol}",
            "canslim": {
                "score": 95,
                "mansfield_rs": mansfield_rs,
                "grid_strategy": grid_strategy or {"mode": "swing", "position": "pilot"},
            },
            "institutional": [],
        }

    return factory


@pytest.fixture
def stock_payload_factory(sample_stock_entry):
    def factory(run_id: str, *, schema_version: str = "1.0") -> dict:
        return {
            "schema_version": schema_version,
            "last_updated": "2026-04-18 20:00:00",
            "run_id": run_id,
            "stocks": {
                "2330": sample_stock_entry("2330", schema_version=schema_version),
                "2317": sample_stock_entry("2317", schema_version=schema_version, mansfield_rs=81.2),
            },
            "industry_strength": [],
        }

    return factory


@pytest.fixture
def summary_payload_factory():
    def factory(run_id: str) -> dict:
        return {
            "timestamp": "2026-04-18 20:00:00",
            "update_type": "bundle publish",
            "description": f"publish run {run_id}",
            "run_id": run_id,
            "api_status": {
                "finmind": "ok",
                "yfinance": "ok",
            },
            "data_stats": {
                "total_stocks": 2,
                "updated_stocks": 2,
            },
        }

    return factory


@pytest.fixture
def artifact_bundle_factory(stock_payload_factory, summary_payload_factory):
    def factory(run_id: str, docs_dir: Path) -> dict[str, dict]:
        return {
            str(docs_dir / "data_base.json"): {
                "artifact_kind": "data_base",
                "payload": stock_payload_factory(run_id),
            },
            str(docs_dir / "data.json"): {
                "artifact_kind": "data",
                "payload": stock_payload_factory(run_id),
            },
            str(docs_dir / "data_light.json"): {
                "artifact_kind": "data_light",
                "payload": stock_payload_factory(run_id),
            },
            str(docs_dir / "data.json.gz"): {
                "artifact_kind": "data_gz",
                "payload": stock_payload_factory(run_id),
            },
            str(docs_dir / "update_summary.json"): {
                "artifact_kind": "update_summary",
                "payload": summary_payload_factory(run_id),
            },
        }

    return factory


@pytest.fixture
def read_artifact():
    def factory(path: Path, artifact_kind: str) -> dict:
        if artifact_kind == "data_gz":
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                return json.load(handle)

        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    return factory
