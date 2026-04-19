import gzip
import json
from pathlib import Path

import pandas as pd
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


@pytest.fixture
def selector_config_factory(tmp_path: Path):
    def factory(payload: dict | None = None) -> tuple[Path, dict]:
        config = {
            "base_symbols": ["1101", "2330"],
            "etf_symbols": ["0050"],
            "watchlist_symbols": ["8069"],
            "target_size": 6,
        }
        if payload:
            config.update(payload)

        path = tmp_path / "core_selection_config.json"
        path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        return path, config

    return factory


@pytest.fixture
def selector_artifact_factory(tmp_path: Path):
    def factory(
        *,
        fused_rows: list[dict],
        master_rows: list[dict] | None = None,
        baseline_rs: dict[str, float] | None = None,
    ) -> dict[str, Path]:
        root = tmp_path / "selector_artifacts"
        docs_dir = root / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        fused_path = root / "master_canslim_signals_fused.parquet"
        master_path = root / "master_canslim_signals.parquet"
        baseline_path = docs_dir / "data_base.json"

        pd.DataFrame(fused_rows).to_parquet(fused_path, index=False)
        pd.DataFrame(master_rows or fused_rows).to_parquet(master_path, index=False)

        baseline_payload = {
            "stocks": {
                symbol: {"canslim": {"mansfield_rs": rs_value}}
                for symbol, rs_value in (baseline_rs or {}).items()
            }
        }
        baseline_path.write_text(
            json.dumps(baseline_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return {
            "root": root,
            "docs": docs_dir,
            "fused_path": fused_path,
            "master_path": master_path,
            "baseline_path": baseline_path,
        }

    return factory


@pytest.fixture
def rotation_state_paths(tmp_path: Path) -> dict[str, Path]:
    root = tmp_path / ".orchestration"
    root.mkdir(parents=True, exist_ok=True)
    return {
        "root": root,
        "state": root / "rotation_state.json",
    }
