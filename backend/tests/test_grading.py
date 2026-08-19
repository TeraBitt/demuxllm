"""Tests for the real-endpoint grading path.

Every case here is one that was actually wrong at some point, or one whose failure
would silently corrupt a headline rather than raise. The normalisation cases in
particular are the specific disagreements found by replaying this comparison over
13,312 records the corpus had already graded — they are pinned so a future tidy-up
cannot quietly reintroduce a 1-2 point bias against the models that write maths.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_grading_set import item_key                                  # noqa: E402
from grade_fireworks import (MAPPING, extract_boxed, grade, norm_math,  # noqa: E402
                             strip_reasoning)


# ------------------------------------------------------------------ extraction --

def test_boxed_handles_nested_braces():
    """\\frac{1}{2} inside \\boxed{} needs depth counting, not a lazy regex."""
    assert extract_boxed(r"so \boxed{\frac{1}{2}}") == r"\frac{1}{2}"


def test_boxed_takes_the_last_one():
    """Models restate earlier candidates; the final one is the answer."""
    assert extract_boxed(r"maybe \boxed{3} ... actually \boxed{7}") == "7"


def test_boxed_absent_is_none():
    assert extract_boxed("I could not solve it") is None


def test_unterminated_boxed_is_not_an_answer():
    """A trace cut off mid-answer must not yield a truncated string as the answer."""
    assert extract_boxed(r"the answer is \boxed{12") is None


def test_letter_grader_takes_the_last_match():
    """'Answer: B' after reasoning that mentioned 'Answer: A' scores against B."""
    text = "Answer: A is tempting.\nOn reflection.\nAnswer: B"
    assert grade("gpqa", "B", text) == (1.0, "B")


def test_reasoning_block_is_not_scanned_for_the_answer():
    """A discarded candidate inside <think> must not be graded as the answer."""
    text = "<think>Answer: A</think>\nAnswer: C"
    assert grade("mmlupro", "C", text) == (1.0, "C")


def test_unclosed_think_block_leaves_nothing_gradeable():
    """Ran out of tokens mid-thought: there is no answer, and that is not a zero."""
    score, pred = grade("gpqa", "B", "<think>reasoning that never finished")
    assert score is None and pred is None


def test_ungradeable_is_none_not_zero():
    """The distinction the whole ledger rests on — see RESULTS.md §4.3."""
    assert grade("aime", "33", "I give up") == (None, None)


# --------------------------------------------------------------- normalisation --

@pytest.mark.parametrize("a,b", [
    ("33", "33.0"),            # same number, two spellings
    (r"336^\circ", "336"),     # unit suffix the corpus ignores
    (r"$115^\circ$", "115"),
    (r"\{2,5\}", "2,5"),       # set braces
    (r"10^{2^n-n-1}", r"10^{2^{n} - n - 1}"),
    (r"\dfrac{1}{2}", r"\frac{1}{2}"),
    (r"\frac{5}{2}", "2.5"),   # rational and its decimal
    (r"\pm 1/n!", r"\pm \dfrac{1}{n!}"),
    (r"\left(3\right)", "(3)"),
    (r"\text{42}", "42"),
])
def test_normalisation_treats_these_as_equal(a, b):
    assert norm_math(a) == norm_math(b)


@pytest.mark.parametrize("a,b", [
    ("33", "34"),
    ("1/2", "1/3"),
    ("x+1", "x+2"),
])
def test_normalisation_keeps_different_answers_different(a, b):
    """The rules rewrite notation; none of them may collapse two real answers."""
    assert norm_math(a) != norm_math(b)


def test_normalisation_does_not_do_algebra():
    """Factored and expanded forms are left to disagree rather than guessed at."""
    assert norm_math(r"8\sqrt{5}-16") != norm_math(r"8(\sqrt{5}-2)")


# --------------------------------------------------------------------- wiring --

def test_item_key_matches_the_corpus_loader():
    """If these two ever diverge, the graded run addresses items that do not exist."""
    from rollingbench.data.llmrouterbench import _item_key
    for ds, prompt in [("aime", "What is 2+2?"), ("gpqa", "  spaced\n\nout  ")]:
        assert item_key(ds, prompt) == _item_key(ds, prompt)


def test_every_mapped_slot_is_a_real_chutes_slot():
    """The mapping is the whole of the assumption; a typo in it is a silent swap."""
    from rollingbench.catalog import CHUTES_CATALOG
    ids = {m.id for m in CHUTES_CATALOG}
    assert set(MAPPING) <= ids


def test_mapping_is_one_to_one():
    """Two slots sharing a Fireworks model would produce duplicate columns."""
    fw = [v["fw"] for v in MAPPING.values()]
    assert len(fw) == len(set(fw))


# ----------------------------------------------------------------- artifact --

def test_saved_artifact_is_indexed_by_its_own_pool(tmp_path):
    """A sub-pool artifact must not carry the full catalogue's price vector.

    `save_artifact` used to write `price_in`/`price_out` straight off CHUTES_CATALOG,
    so a four-model router shipped with thirteen prices. Nothing raises on load — the
    gateway just pairs column 1 with slot 1's price and bills the wrong model.
    """
    import numpy as np
    from rollingbench.data.labelmatrix import LabelMatrix
    from rollingbench.experiments.chutes import save_artifact
    from rollingbench.router import RidgeLinUCBRouter, RouterConfig

    slots = ["zai-org/GLM-5.2-TEE", "moonshotai/Kimi-K3-TEE"]
    n, d = 6, 5
    lm = LabelMatrix(
        item_ids=np.array([f"i{i}" for i in range(n)], dtype=object),
        model_ids=slots,
        quality=np.zeros((n, 2)), cost=np.zeros((n, 2)),
        observed=np.ones((n, 2), dtype=bool), tokens_out=np.ones((n, 2)),
    )
    r = RidgeLinUCBRouter(d, 2, RouterConfig())
    r.fit(np.zeros((n, d)), lm.quality, lm.observed, lm.tokens_out)
    save_artifact(r, lm, tmp_path / "r.npz")

    z = np.load(tmp_path / "r.npz", allow_pickle=True)
    assert len(z["model_ids"]) == 2
    assert len(z["price_in"]) == 2, "price vector must match the pool, not the catalogue"
    assert len(z["price_out"]) == 2
    assert len(z["proxy_ids"]) == 2
    assert z["quality_W"].shape[1] == 2


def test_artifact_round_trips_without_the_corpus(tmp_path):
    """A saved engine must route from the file alone — no corpus, no refit.

    The first version shipped weights without φ. Nothing failed at save time; the
    failure was a dimension error deep in a request path, because the projection's
    rank depends on how many items it was fitted on. φ and the config travel with
    the weights or the artifact is not an engine.
    """
    import numpy as np
    from rollingbench.data.labelmatrix import LabelMatrix
    from rollingbench.experiments.chutes import load_artifact, save_artifact
    from rollingbench.features import FeatureMap
    from rollingbench.router import RidgeLinUCBRouter, RouterConfig

    slots = ["zai-org/GLM-5.2-TEE", "moonshotai/Kimi-K3-TEE"]
    texts = [f"question number {i} about maths and code" for i in range(12)]
    fm = FeatureMap(n_components=4, n_buckets=64).fit(texts)
    X = fm.transform(texts)

    lm = LabelMatrix(
        item_ids=np.array(texts, dtype=object), model_ids=slots,
        quality=np.tile([0.0, 1.0], (12, 1)), cost=np.ones((12, 2)),
        observed=np.ones((12, 2), dtype=bool), tokens_out=np.ones((12, 2)) * 100,
    )
    r = RidgeLinUCBRouter(X.shape[1], 2, RouterConfig(lam=2.0, lam_cost=0.3))
    r.fit(X, lm.quality, lm.observed, lm.tokens_out)
    save_artifact(r, lm, tmp_path / "e.npz", feature_map=fm)

    r2, fm2, pool, ids2 = load_artifact(tmp_path / "e.npz")
    assert ids2 == slots
    assert r2.cfg.lam_cost == 0.3 and r2.cfg.lam == 2.0
    # φ reproduces its own features, and the reloaded router agrees with the original.
    assert np.allclose(fm2.transform(texts), X, atol=1e-8)
    a = np.asarray(getattr(r.decide(X, pool), "choice")).ravel()
    b = np.asarray(getattr(r2.decide(fm2.transform(texts), pool), "choice")).ravel()
    assert (a == b).all()


def test_artifact_without_a_feature_map_refuses_to_load(tmp_path):
    """Better to fail here than to fail as a shape error inside a request."""
    import numpy as np
    import pytest
    from rollingbench.data.labelmatrix import LabelMatrix
    from rollingbench.experiments.chutes import load_artifact, save_artifact
    from rollingbench.router import RidgeLinUCBRouter, RouterConfig

    slots = ["zai-org/GLM-5.2-TEE", "moonshotai/Kimi-K3-TEE"]
    lm = LabelMatrix(
        item_ids=np.array(["a", "b"], dtype=object), model_ids=slots,
        quality=np.zeros((2, 2)), cost=np.zeros((2, 2)),
        observed=np.ones((2, 2), dtype=bool), tokens_out=np.ones((2, 2)),
    )
    r = RidgeLinUCBRouter(3, 2, RouterConfig())
    r.fit(np.zeros((2, 3)), lm.quality, lm.observed, lm.tokens_out)
    save_artifact(r, lm, tmp_path / "old.npz")          # no feature_map=
    with pytest.raises(ValueError, match="no feature map"):
        load_artifact(tmp_path / "old.npz")
