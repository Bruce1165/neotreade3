from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path

import pytest

from apps.api.main import BootstrapApiService
from apps.api.router import BootstrapApiRouter
from apps.api.shared import ApiBinaryResponse, ApiError
from neotrade3.strategy_config import StrategyConfig, save_strategy_config


def _write_strategy_config(
    *,
    project_root: Path,
    strategy_id: str,
    version: int = 1,
    description: str = "",
    parameters: dict[str, object] | None = None,
) -> None:
    config = StrategyConfig(
        strategy_id=strategy_id,
        version=version,
        description=description,
        parameters=parameters or {},
    )
    save_strategy_config(project_root=project_root, config=config)


def test_strategies_list_endpoint_returns_configs_sorted_by_strategy_id(
    tmp_path: Path,
) -> None:
    _write_strategy_config(
        project_root=tmp_path,
        strategy_id="b",
        version=1,
    )
    _write_strategy_config(
        project_root=tmp_path,
        strategy_id="a",
        version=2,
    )

    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/strategies?limit=20")

    assert status == HTTPStatus.OK
    assert payload["_meta"]["returned_count"] == 2
    assert [item["strategy_id"] for item in payload["strategies"]] == ["a", "b"]


def test_strategies_list_endpoint_fails_closed_when_invalid_json_exists(
    tmp_path: Path,
) -> None:
    _write_strategy_config(
        project_root=tmp_path,
        strategy_id="ok",
        version=1,
    )
    base_dir = tmp_path / "config/strategies"
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "broken.json").write_text("{", encoding="utf-8")

    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/strategies")

    assert exc.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert exc.value.code == "strategy_config_invalid"


def test_strategy_readback_endpoint_returns_payload(
    tmp_path: Path,
) -> None:
    _write_strategy_config(
        project_root=tmp_path,
        strategy_id="lowfreq_v16",
        version=1,
        parameters={"BUY_THRESHOLD": 85.0},
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/strategies/lowfreq_v16")

    assert status == HTTPStatus.OK
    assert payload["_meta"]["status"] == "ok"
    assert payload["strategy_config"]["strategy_id"] == "lowfreq_v16"
    assert payload["strategy_config"]["parameters"]["BUY_THRESHOLD"] == 85.0


def test_strategy_readback_endpoint_returns_404_when_missing(
    tmp_path: Path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/strategies/missing_strategy")

    assert exc.value.status_code == HTTPStatus.NOT_FOUND
    assert exc.value.code == "strategy_config_not_found"


def test_strategy_readback_endpoint_returns_400_for_path_traversal_strategy_id(
    tmp_path: Path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/strategies/..")

    assert exc.value.status_code == HTTPStatus.BAD_REQUEST
    assert exc.value.code == "invalid_strategy_id"


def test_strategy_download_endpoint_returns_attachment(
    tmp_path: Path,
) -> None:
    _write_strategy_config(
        project_root=tmp_path,
        strategy_id="lowfreq_v16",
        version=1,
        parameters={"BUY_THRESHOLD": 85.0},
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch("/api/strategies/lowfreq_v16/download")

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    assert "attachment" in response.headers.get("Content-Disposition", "")
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["strategy_id"] == "lowfreq_v16"

