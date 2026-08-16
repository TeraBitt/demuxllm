# Convenience targets. Everything works without make; these are the four commands.
PY := .venv/bin/python

.PHONY: help setup data run quick notebooks test all clean chutes-data chutes export-frontend

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

test:
	$(PY) -m pytest tests/ -q

all: data run notebooks test

clean:
	rm -rf artifacts/*.json artifacts/figures data/cache
