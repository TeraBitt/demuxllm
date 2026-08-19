# Convenience targets. Everything works without make; these are the four commands.
PY := .venv/bin/python

.PHONY: help setup data run quick notebooks test all clean chutes-data chutes export-frontend publish latency latency-plan

help:
	@echo "setup        create .venv and install requirements"
	@echo "data         download RouterBench (~95 MB, once)"
	@echo "run          run every experiment, write artifacts/ and figures"
	@echo "quick        same, with smaller replays (a few minutes)"
	@echo "notebooks    rebuild and execute the notebooks against artifacts/"
	@echo "test         run the test suite"
	@echo "all          data + run + notebooks + test"
	@echo ""
	@echo "chutes-data  parse LLMRouterBench into the 13-model cache (once, ~4 min)"
	@echo "chutes       train and analyse the router over the Chutes pool (~15s)"
	@echo "export-frontend  regenerate src/lib/measured.ts from artifacts/"
	@echo ""
	@echo "publish      close PUBLISHABILITY.md §6 as far as compute can (~17 min)"
	@echo "latency-plan what a timed endpoint run would cost (free, offline)"
	@echo "latency      the timed run itself (needs FIREWORKS_API_KEY)"

setup:
	python3 -m venv .venv && $(PY) -m pip install -q --upgrade pip && $(PY) -m pip install -q -r requirements.txt

data:
	$(PY) scripts/fetch_data.py --corpus routerbench

run:
	$(PY) scripts/run_all.py

quick:
	$(PY) scripts/run_all.py --quick

notebooks:
	$(PY) scripts/build_notebooks.py && $(PY) scripts/execute_notebooks.py

# The Chutes pool — the thirteen models the product actually serves.
# `chutes-data` streams the LLMRouterBench archive; it never extracts it, because
# expanding it fills a normal disk.
chutes-data:
	$(PY) scripts/build_chutes_matrix.py

chutes:
	$(PY) scripts/train_chutes.py

# Regenerate src/lib/measured.ts from the artifacts. Run after `run` or `chutes`;
# the site imports it, so a stale file is a stale claim on a public page.
export-frontend:
	$(PY) scripts/export_measured.py --write

# The real graded run. `grading-set` is free and offline; `grade` spends money and
# needs FIREWORKS_API_KEY. Both budget ceilings are hard — the run stops on an item
# boundary when either is reached, which is what keeps the output dense.
grading-set:
	$(PY) scripts/build_grading_set.py --verify

grade:
	$(PY) scripts/grade_fireworks.py --batch 12 --budget-usd 33.0 --budget-tokens 100000000

grade-export:
	$(PY) scripts/export_graded.py

# Route over the real pool, then A/B the thirteen-slot router with the measured
# columns swapped in. Both read artifacts/grading/matrix.npz.
grade-analyze:
	$(PY) scripts/analyze_graded.py
	$(PY) scripts/retrain_hybrid.py

# Train the engine on our own measurements only and ship a loadable artifact.
grade-train:
	$(PY) scripts/train_real.py

# The second pass over PUBLISHABILITY.md §6 — everything on that list that compute
# can close rather than money. Offline, ~17 minutes, no key.
publish:
	$(PY) scripts/publish_close.py

# Latency in seconds. `plan` is free and offline and prints what a real run costs;
# `run` needs FIREWORKS_API_KEY and spends a few dollars. `run --dry-run` exercises
# the whole path with synthetic timings that are stamped so they cannot be quoted.
latency-plan:
	$(PY) scripts/measure_latency.py plan

latency:
	$(PY) scripts/measure_latency.py run && $(PY) scripts/measure_latency.py analyse

test:
	$(PY) -m pytest tests/ -q

all: data run notebooks test

clean:
	rm -rf artifacts/*.json artifacts/figures data/cache
