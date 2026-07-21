from __future__ import annotations

from pathlib import Path


def test_rulebook_includes_hazard_label_prediction_separation_constraints() -> None:
    rulebook = Path("docs/architecture/lowfreq_v16_model_rulebook.md").read_text(encoding="utf-8")
    assert "Label/Prediction 严格分离" in rulebook
    assert "No-lookahead" in rulebook
    assert "stock_top_hazard_labels_t2" in rulebook
    assert "hazard_state" in rulebook
