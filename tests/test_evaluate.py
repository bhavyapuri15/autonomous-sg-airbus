import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evaluation"))
import evaluate as E  # noqa: E402
import split as S  # noqa: E402


def test_locked_without_final_raises():
    with pytest.raises(PermissionError):
        E.main(["--split", "locked", "--no-write"])
    with pytest.raises(PermissionError):
        E.load_cases("F1", "locked", final=False)
    with pytest.raises(PermissionError):
        S.assert_not_locked(S.LOCKED_DIR / "f1_id_lookup.jsonl")


def test_recall_at_k():
    assert E.recall_at_k(["a", "b", "c"], {"c"}, 3) == 1.0
    assert E.recall_at_k(["a", "b", "c"], {"c"}, 2) == 0.0
    assert E.recall_at_k([], {"x"}, 5) == 0.0


def test_mrr():
    assert E.reciprocal_rank(["a", "b", "c"], {"b", "c"}) == 0.5
    assert E.reciprocal_rank(["a", "b"], {"z"}) == 0.0
    assert E.reciprocal_rank(["a", "b", "c"], {"c"}, k=2) == 0.0
    assert E.mean([1.0, 0.5, 0.0]) == 0.5


def test_precision_recall():
    # abstain-positive: 2 TP, 1 FP, 1 FN, 2 TN
    pred = [True, True, True, False, False, False]
    gold = [True, True, False, True, False, False]
    r = E.precision_recall_f1(pred, gold)
    assert (r["tp"], r["fp"], r["fn"], r["tn"]) == (2, 1, 1, 2)
    assert r["precision"] == round(2 / 3, 4) and r["recall"] == round(2 / 3, 4) and r["f1"] == round(2 / 3, 4)
    assert E.precision_recall_f1([False], [False])["precision"] is None


def test_percentile_and_overlap_and_norm():
    assert E.percentile([1, 2, 3, 4, 5], 50) == 3
    assert E.percentile([], 50) is None
    assert E.spans_overlap(0, 10, 9, 20) and not E.spans_overlap(0, 10, 10, 20)
    assert E.norm_text("A–B  “x”") == 'a-b "x"'
