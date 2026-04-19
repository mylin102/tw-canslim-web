from importlib import import_module
import os


def load_orchestration_state_module():
    return import_module("orchestration_state")


def test_load_rotation_state_seeds_default_payload(rotation_state_paths):
    module = load_orchestration_state_module()

    state = module.load_rotation_state(path=str(rotation_state_paths["state"]))

    assert state == {
        "schema_version": "1.0",
        "current_batch_index": 0,
        "rotation_generation": "",
        "retry_queue": [],
        "freshness": {},
        "in_progress": None,
        "last_completed_batch": None,
    }
    assert rotation_state_paths["state"].exists()


def test_save_rotation_state_writes_atomically_and_preserves_fields(
    monkeypatch,
    rotation_state_paths,
):
    module = load_orchestration_state_module()
    observed_calls = []
    original_replace = os.replace

    def tracking_replace(source, destination):
        observed_calls.append((source, destination))
        return original_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", tracking_replace)

    expected_state = {
        "schema_version": "1.0",
        "current_batch_index": 2,
        "rotation_generation": "gen-2026-04-19",
        "retry_queue": [
            {
                "symbol": "2330",
                "provider": "finmind",
                "error": "timeout",
                "attempt_count": 1,
                "failed_at": "2026-04-19T00:00:00Z",
                "due_at": "2026-04-19T00:05:00Z",
                "batch_index": 2,
                "rotation_generation": "gen-2026-04-19",
            }
        ],
        "freshness": {
            "2330": {
                "last_success_at": "2026-04-19T00:00:00Z",
                "source": "rotation",
            }
        },
        "in_progress": {
            "batch_index": 2,
            "rotation_generation": "gen-2026-04-19",
            "symbols": ["2330", "2317"],
            "completed_symbols": ["2330"],
            "remaining_symbols": ["2317"],
        },
        "last_completed_batch": {
            "batch_index": 1,
            "rotation_generation": "gen-2026-04-18",
            "completed_at": "2026-04-18T23:59:59Z",
            "symbol_count": 2,
        },
    }

    module.save_rotation_state(expected_state, path=str(rotation_state_paths["state"]))

    assert observed_calls
    assert observed_calls[0][1] == str(rotation_state_paths["state"])
    assert module.load_rotation_state(path=str(rotation_state_paths["state"])) == expected_state


def test_enqueue_retry_failure_persists_failed_symbol_metadata(rotation_state_paths):
    module = load_orchestration_state_module()
    module.load_rotation_state(path=str(rotation_state_paths["state"]))

    queued = module.enqueue_retry_failure(
        path=str(rotation_state_paths["state"]),
        symbol="2454",
        provider="requests",
        error="503 service unavailable",
        due_at="2026-04-19T01:00:00Z",
        failed_at="2026-04-19T00:58:00Z",
        batch_index=0,
        rotation_generation="gen-2026-04-19",
    )

    assert queued["retry_queue"] == [
        {
            "symbol": "2454",
            "provider": "requests",
            "error": "503 service unavailable",
            "attempt_count": 1,
            "failed_at": "2026-04-19T00:58:00Z",
            "due_at": "2026-04-19T01:00:00Z",
            "batch_index": 0,
            "rotation_generation": "gen-2026-04-19",
        }
    ]
    assert module.load_rotation_state(path=str(rotation_state_paths["state"]))["retry_queue"] == queued["retry_queue"]
