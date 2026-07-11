from __future__ import annotations

from pathlib import Path

from apps.api.main import BootstrapApiService


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _make_service() -> BootstrapApiService:
    return BootstrapApiService(project_root=PROJECT_ROOT)


def test_lowfreq_api_normalize_execution_block_reason_reuses_shared_aliases() -> None:
    service = _make_service()

    assert service._lowfreq_normalize_execution_block_reason("no_slots") == "positions_full"
    assert service._lowfreq_normalize_execution_block_reason("reserved_due_to_full_book") == "positions_full"
    assert service._lowfreq_normalize_execution_block_reason("no_cash") == "cash_insufficient"
    assert service._lowfreq_normalize_execution_block_reason("reservation_expired") == "entry_window_missed"
    assert (
        service._lowfreq_normalize_execution_block_reason("pending_conflict_older_intent_wins")
        == "conflict_with_exit"
    )


def test_lowfreq_api_normalize_execution_block_reason_keeps_local_aliases() -> None:
    service = _make_service()

    assert service._lowfreq_normalize_execution_block_reason("signal_expired") == "entry_window_missed"
    assert service._lowfreq_normalize_execution_block_reason("no_open_price") == "execution_rule_blocked"
    assert service._lowfreq_normalize_execution_block_reason("already_holding") == "execution_rule_blocked"
    assert service._lowfreq_normalize_execution_block_reason("position_missing") == "execution_rule_blocked"
    assert service._lowfreq_normalize_execution_block_reason("no_shares") == "execution_rule_blocked"
    assert service._lowfreq_normalize_execution_block_reason("abandoned") == "execution_rule_blocked"


def test_lowfreq_api_normalize_execution_block_reason_keeps_unknown_reason() -> None:
    service = _make_service()

    assert service._lowfreq_normalize_execution_block_reason("custom_reason") == "custom_reason"


def test_lowfreq_execution_contract_from_intent_keeps_api_local_block_reason() -> None:
    service = _make_service()

    contract = service._lowfreq_execution_contract_from_intent(
        {
            "intent_type": "buy_intent",
            "status": "cancelled",
            "cancel_reason": "already_holding",
        }
    )

    assert contract == {
        "source_layer": "execution",
        "action_type": "block",
        "order_action": "block",
        "reserve_action": "",
        "execution_status": "cancelled",
        "execution_block_reason": "execution_rule_blocked",
    }
