from http import HTTPStatus

import pytest

from apps.api.main_modular import ModularApiHandler
from apps.api.utils.errors import ApiError


def _build_handler() -> ModularApiHandler:
    return ModularApiHandler.__new__(ModularApiHandler)


@pytest.mark.parametrize(
    ("method_name", "payload"),
    [
        ("_hot_sectors", {}),
        ("_update_data", {}),
        ("_run_model", {}),
        ("_run_all_screeners", {}),
    ],
)
def test_unimplemented_modular_endpoints_raise_not_implemented(
    method_name: str, payload: dict
) -> None:
    handler = _build_handler()

    with pytest.raises(ApiError) as exc_info:
        getattr(handler, method_name)(payload)

    assert exc_info.value.status_code == HTTPStatus.NOT_IMPLEMENTED
    assert exc_info.value.code == "NOT_IMPLEMENTED"


def test_list_screeners_raises_internal_error_when_registry_load_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler = _build_handler()

    def _raise_registry_error():
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "neotrade3.screeners.registry.load_screener_registry",
        _raise_registry_error,
    )

    with pytest.raises(ApiError) as exc_info:
        handler._list_screeners({})

    assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert exc_info.value.code == "SCREENERS_REGISTRY_ERROR"
