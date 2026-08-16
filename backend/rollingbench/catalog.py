"""Model pools.

Two catalogues live here and they answer different questions.

`CHUTES_CATALOG` mirrors `src/lib/dashboard/models.ts` field for field — the pool
the product actually routes over. It is what the serving-side numbers (savings,
blended price, tier mix) must be computed against, because those are the models a
customer's request can really be sent to.

`ROUTERBENCH_POOL` is the eleven models RouterBench measured. It carries release
dates, which is the one thing the Chutes catalogue cannot supply and the one thing
the staleness study needs: a pool that grows over calendar time. Dates are the
public announcement dates for each model, not dataset artefacts.

`CHUTES_PROXY` is the bridge between them, and it is the one thing in this package
that is an *assumption* rather than a measurement. Read its docstring before
quoting any number computed through it.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

Tier = str  # "open" | "mid" | "frontier"


@dataclass(frozen=True)
class Model:
    """A candidate the router may pick.

    Prices are USD per million tokens, the unit every provider quotes in, so a
    price read off a pricing page can be pasted in without conversion.
    """

    id: str
    label: str
    family: str
    tier: Tier
    in_per_1m: float
    out_per_1m: float
    ctx: int | None = None
    structured: bool = True
    thinks: bool = False
    released: _dt.date | None = None
    good_at: str = ""

    @property
    def blended_price(self) -> float:
        """Output-weighted price, matching `blendedPrice` in the frontend.

        Output tokens are weighted 3x because that is where the spread between
        models lives; a router that compares input prices compares the cheap half
        of the bill.
        """
        return self.in_per_1m + self.out_per_1m * 3

    def cost(self, tokens_in: float, tokens_out: float) -> float:
        return tokens_in / 1e6 * self.in_per_1m + tokens_out / 1e6 * self.out_per_1m


# --------------------------------------------------------------------- chutes --
# Mirrors src/lib/dashboard/models.ts. Keep in sync via scripts/check_catalog.py.

CHUTES_CATALOG: tuple[Model, ...] = (
    Model("Nemotron-3-Nano-Omni-30B-TEE", "Nemotron 3 Nano Omni 30B", "nvidia", "open",
          0.0245, 0.0978, None, structured=False, thinks=False,
          good_at="Extraction, tagging and cleanup"),
    Model("unsloth/Mistral-Nemo-Instruct-2407-TEE", "Mistral Nemo Instruct", "mistral", "open",
          0.0245, 0.0978, None, structured=False, thinks=False,
          good_at="Rewriting and short everyday replies"),
    Model("deepseek-ai/DeepSeek-V4-Flash-0731-TEE", "DeepSeek V4 Flash", "deepseek", "open",
          0.14, 0.28, 1_048_576, thinks=True,
          good_at="Cheap long-context work"),
    Model("google/gemma-4-31B-turbo-TEE", "Gemma 4 31B Turbo", "google", "open",
          0.12, 0.37, 131_072, thinks=True,
          good_at="Everyday questions at low cost"),
    Model("Qwen/Qwen3-32B-TEE", "Qwen3 32B", "qwen", "open",
          0.104, 0.416, 40_960, thinks=True,
          good_at="Classification and structured output"),
    Model("Qwen/Qwen3-235B-A22B-Thinking-2507-TEE", "Qwen3 235B Thinking", "qwen", "mid",
          0.2989, 1.1957, 262_144, thinks=True,
          good_at="Multi-step reasoning"),
    Model("deepseek-ai/DeepSeek-V3.2-TEE", "DeepSeek V3.2", "deepseek", "mid",
          1.0, 1.0, 131_072, thinks=True,
          good_at="Balanced general work"),
    Model("Qwen/Qwen3.6-27B-TEE", "Qwen3.6 27B", "qwen", "mid",
          0.3, 2.0, 262_144, thinks=True,
          good_at="Code and analysis"),
    Model("Qwen/Qwen3.5-397B-A17B-TEE", "Qwen3.5 397B", "qwen", "mid",
          0.45, 3.0, 262_144, thinks=True,
          good_at="Hard reasoning at mid price"),
    Model("zai-org/GLM-5.1-TEE", "GLM 5.1", "zai", "mid",
          0.98, 3.08, 202_752, thinks=True,
          good_at="Agentic tool use"),
    Model("moonshotai/Kimi-K2.6-TEE", "Kimi K2.6", "moonshot", "mid",
          0.58, 3.4, 262_144, thinks=True,
          good_at="Long-form writing and agents"),
    Model("zai-org/GLM-5.2-TEE", "GLM 5.2", "zai", "frontier",
          1.25, 3.95, 1_048_576, thinks=True,
          good_at="Frontier reasoning, long context"),
    Model("moonshotai/Kimi-K3-TEE", "Kimi K3", "moonshot", "frontier",
          3.0, 15.0, 1_048_576, thinks=True,
          good_at="The hardest work, price no object"),
)

ORCHESTRATOR_ID = "Qwen/Qwen3-32B-TEE"
BASELINE_ID = "moonshotai/Kimi-K3-TEE"


# ---------------------------------------------------------------- routerbench --
# The eleven models RouterBench ran. `released` is the public announcement date;
# it is what lets §14.1 replay a pool that grows, which is the whole experiment.
# Prices are the per-1M list prices in force when RouterBench was collected, kept
# only for reference — the label matrix ships realised per-call cost, so the
# experiments read that rather than re-deriving it.

ROUTERBENCH_POOL: tuple[Model, ...] = (
    Model("claude-instant-v1", "Claude Instant v1", "anthropic", "open",
          0.80, 2.40, 100_000, released=_dt.date(2023, 3, 14)),
    Model("claude-v1", "Claude v1", "anthropic", "mid",
          8.00, 24.00, 100_000, released=_dt.date(2023, 3, 14)),
    Model("mistralai/mistral-7b-chat", "Mistral 7B Instruct", "mistral", "open",
          0.20, 0.20, 8_192, released=_dt.date(2023, 9, 27)),
    Model("WizardLM/WizardLM-13B-V1.2", "WizardLM 13B v1.2", "wizardlm", "open",
          0.30, 0.30, 4_096, released=_dt.date(2023, 7, 25)),
    Model("meta/llama-2-70b-chat", "Llama 2 70B Chat", "meta", "open",
          0.90, 0.90, 4_096, released=_dt.date(2023, 7, 18)),
    Model("meta/code-llama-instruct-34b-chat", "Code Llama 34B Instruct", "meta", "open",
          0.78, 0.78, 16_384, released=_dt.date(2023, 8, 24)),
    Model("claude-v2", "Claude v2", "anthropic", "mid",
          8.00, 24.00, 100_000, released=_dt.date(2023, 7, 11)),
    Model("gpt-3.5-turbo-1106", "GPT-3.5 Turbo (1106)", "openai", "open",
          1.00, 2.00, 16_385, released=_dt.date(2023, 11, 6)),
    Model("gpt-4-1106-preview", "GPT-4 Turbo (1106)", "openai", "frontier",
          10.00, 30.00, 128_000, released=_dt.date(2023, 11, 6)),
    Model("zero-one-ai/Yi-34B-Chat", "Yi 34B Chat", "01ai", "mid",
          0.80, 0.80, 4_096, released=_dt.date(2023, 11, 23)),
    Model("mistralai/mixtral-8x7b-chat", "Mixtral 8x7B Instruct", "mistral", "mid",
          0.60, 0.60, 32_768, released=_dt.date(2023, 12, 11)),
)


# ---------------------------------------------------------------- the bridge --


@dataclass(frozen=True)
class ProxyBinding:
    """One Chutes model, and the measured model standing in for it.

    `why` is not decoration. Each binding is a judgement that can be wrong, and the
    reader deserves to see which ones are near-identities and which are guesses.
    """

    chutes_id: str
    proxy_id: str
    why: str
    #: True only where the measured checkpoint *is* the catalogue entry.
    exact: bool = False
    #: True where the stand-in comes from the same model family.
    same_family: bool = False


# Every model Chutes serves is open-weights, so a stand-in that is not is a weaker
# analogue than its capability score suggests — it was trained and served under
# different constraints. Tracked explicitly so `experiments/chutes.open_weights_only`
# can measure what insisting on open stand-ins would cost, rather than leaving it to
# an argument.
OPEN_WEIGHT_PROXIES: frozenset[str] = frozenset({
    # large
    "qwen3-235b-a22b-thinking-2507", "qwen3-235b-a22b-2507", "deepseek-r1-0528",
    "deepseek-v3.1-terminus", "deepseek-v3-0324", "glm-4.6", "kimi-k2-0905",
    "intern-s1",
    # small
    "Qwen3-8B", "DeepSeek-R1-0528-Qwen3-8B", "DeepSeek-R1-Distill-Qwen-7B",
    "Qwen2.5-Coder-7B-Instruct", "gemma-2-9b-it", "glm-4-9b-chat",
    "GLM-Z1-9B-0414", "NVIDIA-Nemotron-Nano-9B-v2", "Llama-3.1-Nemotron-Nano-8B-v1",
    "Llama-3.1-8B-Instruct", "Llama-3.1-8B-UltraMedical", "MiniCPM4.1-8B",
    "Intern-S1-mini", "internlm3-8b-instruct", "granite-3.3-8b-instruct",
    "OpenThinker3-7B", "MiMo-7B-RL-0530", "cogito-v1-preview-llama-8B",
    "DeepHermes-3-Llama-3-8B-Preview", "Fin-R1",
})

#: Stand-ins whose weights are not published. Usable as capability anchors, but a
#: worse analogue for a pool of open models than their score alone implies.
CLOSED_WEIGHT_PROXIES: frozenset[str] = frozenset({
    "gpt-5", "gpt-5-chat", "gemini-2.5-pro", "gemini-2.5-flash", "claude-sonnet-4",
})


# Public announcement dates for the stand-in checkpoints, attached by hand from the
# labs' own release posts — exactly as `ROUTERBENCH_POOL` does, and for the same
# reason: LLMRouterBench publishes no dates, and without them there is no way to
# replay a pool that grows over calendar time.
#
# These are the one input in the Chutes half of this package that is neither
# measured nor read from an API. They are dates, not measurements, so a wrong one
# shifts *when* a model joins the replay and nothing else — it cannot change any
# model's quality or price. Month granularity throughout, pinned to the first of the
# month, because that is the resolution the announcements support and a replay that
# implied day-accuracy would be claiming more than is known.
PROXY_RELEASED: dict[str, _dt.date] = {
    # 2024 — the small open models
    "glm-4-9b-chat": _dt.date(2024, 6, 1),
    "gemma-2-9b-it": _dt.date(2024, 6, 1),
    "Llama-3.1-8B-Instruct": _dt.date(2024, 7, 1),
    "Llama-3.1-8B-UltraMedical": _dt.date(2024, 8, 1),
    "Qwen2.5-Coder-7B-Instruct": _dt.date(2024, 9, 1),
    "granite-3.3-8b-instruct": _dt.date(2024, 10, 1),
    "DeepHermes-3-Llama-3-8B-Preview": _dt.date(2024, 12, 1),
    # 2025 — reasoning distils, then the large open models
    "DeepSeek-R1-Distill-Qwen-7B": _dt.date(2025, 1, 1),
    "internlm3-8b-instruct": _dt.date(2025, 1, 1),
    "Llama-3.1-Nemotron-Nano-8B-v1": _dt.date(2025, 3, 1),
    "deepseek-v3-0324": _dt.date(2025, 3, 1),
    "gemini-2.5-pro": _dt.date(2025, 3, 1),
    "GLM-Z1-9B-0414": _dt.date(2025, 4, 1),
    "Qwen3-8B": _dt.date(2025, 4, 1),
    "cogito-v1-preview-llama-8B": _dt.date(2025, 4, 1),
    "MiMo-7B-RL-0530": _dt.date(2025, 5, 1),
    "deepseek-r1-0528": _dt.date(2025, 5, 1),
    "DeepSeek-R1-0528-Qwen3-8B": _dt.date(2025, 5, 1),
    "OpenThinker3-7B": _dt.date(2025, 6, 1),
    "Fin-R1": _dt.date(2025, 6, 1),
    "MiniCPM4.1-8B": _dt.date(2025, 6, 1),
    "qwen3-235b-a22b-2507": _dt.date(2025, 7, 1),
    "qwen3-235b-a22b-thinking-2507": _dt.date(2025, 7, 1),
    "intern-s1": _dt.date(2025, 7, 1),
    "Intern-S1-mini": _dt.date(2025, 8, 1),
    "gpt-5": _dt.date(2025, 8, 1),
    "NVIDIA-Nemotron-Nano-9B-v2": _dt.date(2025, 8, 1),
    "kimi-k2-0905": _dt.date(2025, 9, 1),
    "deepseek-v3.1-terminus": _dt.date(2025, 9, 1),
    "glm-4.6": _dt.date(2025, 10, 1),
}


def chutes_released() -> dict[str, _dt.date]:
    """Release date per *Chutes* slot, inherited from its stand-in.

    The Chutes catalogue carries no dates of its own — it is a forward-looking
    product pool. The stand-in's date is what the replay uses, which is the honest
    reading: the slot became routable when a model of that capability existed.
    """
    return {b.chutes_id: PROXY_RELEASED[b.proxy_id]
            for b in CHUTES_PROXY if b.proxy_id in PROXY_RELEASED}


def chutes_dated() -> tuple[Model, ...]:
    """`CHUTES_CATALOG` with release dates attached, for the growing-pool replay.

    Kept as a function rather than a second constant so there is exactly one
    catalogue in the package and no chance of the two drifting apart.
    """
    import dataclasses

    dates = chutes_released()
    return tuple(dataclasses.replace(m, released=dates.get(m.id)) for m in CHUTES_CATALOG)


# CHUTES_PROXY — where the 13-model pool's *behaviour* comes from.
#
# Nothing in this repository can measure a Chutes endpoint: the catalogue is a
# forward-looking product pool and no public label matrix grades those checkpoints.
# So each Chutes slot is bound to a model LLMRouterBench *did* grade, and the router
# is trained on that column's real per-item outcomes.
#
# What this buys and what it costs, stated plainly:
#
#   • Quality and output-token behaviour are REAL measurements — of the proxy, on
#     3,932 dense items across nine tasks, graded by the corpus's own graders.
#   • Price is REAL and is the Chutes list price, not the proxy's. Cost per cell is
#     recomputed as (measured tokens x published Chutes price), which is exactly the
#     split the architecture already makes: prices are read live and never fitted.
#   • The binding itself is an ASSUMPTION. "DeepSeek V3.2 will behave like
#     deepseek-v3.1-terminus" is a claim about a model nobody here has run.
#
# Every artifact written through this table carries `proxy_backed: true`, and every
# figure derived from it is labelled, so no number computed here can be mistaken for
# a measurement of Chutes itself. Swap in a real graded run and every downstream
# number recomputes with no other edit — that is the point of keeping the binding in
# one table.
#
# Bindings are chosen family-first, then on measured capability so that the pool's
# capability ladder does not contradict its price ladder. Two slots could not have
# both; they are marked and named below.
CHUTES_PROXY: tuple[ProxyBinding, ...] = (
    ProxyBinding(
        "Nemotron-3-Nano-Omni-30B-TEE", "NVIDIA-Nemotron-Nano-9B-v2",
        "Same family and size class — NVIDIA's Nemotron Nano line, small and non-thinking.",
        same_family=True),
    ProxyBinding(
        "unsloth/Mistral-Nemo-Instruct-2407-TEE", "Llama-3.1-8B-Instruct",
        "No Mistral checkpoint is graded anywhere in the corpus. The closest measured "
        "analogue is a small non-thinking general instruct model of the same generation.",
        same_family=False),
    ProxyBinding(
        "deepseek-ai/DeepSeek-V4-Flash-0731-TEE", "DeepSeek-R1-0528-Qwen3-8B",
        "DeepSeek family, small 'flash' class, reasoning-capable — matching the "
        "catalogue entry's thinks=True at the cheap end of the pool.",
        same_family=True),
    ProxyBinding(
        "google/gemma-4-31B-turbo-TEE", "gemma-2-9b-it",
        "Gemma family; the only Google open-weights model the corpus grades.",
        same_family=True),
    ProxyBinding(
        "Qwen/Qwen3-32B-TEE", "Qwen3-8B",
        "Qwen3 generation, dense open model — same line, one size class down.",
        same_family=True),
    ProxyBinding(
        "Qwen/Qwen3-235B-A22B-Thinking-2507-TEE", "qwen3-235b-a22b-thinking-2507",
        "The identical checkpoint. The catalogue id and the measured id name the same "
        "weights, so this column is not a proxy at all.",
        exact=True, same_family=True),
    ProxyBinding(
        "deepseek-ai/DeepSeek-V3.2-TEE", "deepseek-v3.1-terminus",
        "DeepSeek V3 line, adjacent point release.",
        same_family=True),
    ProxyBinding(
        "Qwen/Qwen3.6-27B-TEE", "intern-s1",
        "WEAKEST BINDING IN THE TABLE. No Qwen checkpoint is left unassigned at this "
        "capability, so this slot is matched on measured capability and mid-tier price "
        "alone. The family is wrong and the 'code and analysis' speciality is not "
        "reproduced; treat this column's per-task profile as the least trustworthy.",
        same_family=False),
    ProxyBinding(
        "Qwen/Qwen3.5-397B-A17B-TEE", "qwen3-235b-a22b-2507",
        "Qwen large MoE, non-thinking — same architecture class as the catalogue entry.",
        same_family=True),
    ProxyBinding(
        "zai-org/GLM-5.1-TEE", "glm-4.6",
        "GLM family, the strongest GLM checkpoint the corpus grades.",
        same_family=True),
    ProxyBinding(
        "moonshotai/Kimi-K2.6-TEE", "kimi-k2-0905",
        "Kimi K2 line — the catalogue entry is a later point release of these weights.",
        same_family=True),
    ProxyBinding(
        "zai-org/GLM-5.2-TEE", "gemini-2.5-pro",
        "Family unmatched, and deliberately so. A frontier slot needs a column that "
        "beats every mid-tier model, and glm-4.6 — already bound to GLM 5.1 — is the "
        "only GLM measured and does not clear that bar. Capability-matched instead.",
        same_family=False),
    ProxyBinding(
        "moonshotai/Kimi-K3-TEE", "gpt-5",
        "The strongest measured column in the corpus, matching the catalogue entry's "
        "'the hardest work, price no object'.",
        same_family=False),
)


def proxy_ids() -> list[str]:
    """Measured model ids, in `CHUTES_CATALOG` order."""
    return [b.proxy_id for b in CHUTES_PROXY]


def proxy_for(chutes_id: str) -> ProxyBinding:
    for b in CHUTES_PROXY:
        if b.chutes_id == chutes_id:
            return b
    raise KeyError(chutes_id)


def check_proxy_table() -> None:
    """Fail loudly if the bridge and the catalogue drift apart.

    A pool with a duplicated proxy has two identical columns, which silently breaks
    every argmax downstream, so distinctness is checked rather than assumed.
    """
    cat = [m.id for m in CHUTES_CATALOG]
    bound = [b.chutes_id for b in CHUTES_PROXY]
    if cat != bound:
        missing = set(cat) - set(bound)
        extra = set(bound) - set(cat)
        raise ValueError(
            f"CHUTES_PROXY does not cover CHUTES_CATALOG: missing={sorted(missing)} "
            f"extra={sorted(extra)}"
        )
    proxies = proxy_ids()
    dupes = {p for p in proxies if proxies.count(p) > 1}
    if dupes:
        raise ValueError(f"CHUTES_PROXY binds two Chutes models to one proxy: {sorted(dupes)}")


def by_id(pool: tuple[Model, ...], model_id: str) -> Model:
    for m in pool:
        if m.id == model_id:
            return m
    raise KeyError(model_id)


def pool_ids(pool: tuple[Model, ...]) -> list[str]:
    return [m.id for m in pool]


def released_by(pool: tuple[Model, ...], cutoff: _dt.date) -> list[str]:
    """Ids of models announced on or before `cutoff`.

    A router cannot select a column that does not exist yet; this is the filter
    that keeps a replay honest about that.
    """
    return [m.id for m in pool if m.released is not None and m.released <= cutoff]
