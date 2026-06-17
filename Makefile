# hermesbench Makefile
# Q70: `make demo` runs an end-to-end demo.

.PHONY: help demo doctor test lint install clean run-all

help:
	@echo "hermesbench Makefile"
	@echo ""
	@echo "  make demo       - one-task end-to-end demo (Q70)"
	@echo "  make doctor     - pre-flight checks (Q70)"
	@echo "  make test       - run the test suite (excludes integration)"
	@echo "  make lint       - run lints (verifier stdlib, fixture size, fixture injection)"
	@echo "  make install    - editable pip install"
	@echo "  make run-all    - run all 48 tasks (requires a model server)"
	@echo "  make clean      - remove traces/ and results/"

demo:
	python3 -m hermesbench doctor
	python3 -m scripts.fake_model_server &
	@sleep 2
	python3 -m hermesbench run --task t01_terminal_smoke/t01_echo \
		--model fake --base-url http://127.0.0.1:8080/v1
	@kill %1 2>/dev/null || true

doctor:
	python3 -m hermesbench doctor

test:
	python3 -m pytest tests/ -m "not integration" -v

lint:
	python3 -m pytest tests/test_lint_verifiers.py tests/test_lint_fixtures.py tests/test_lint_fixture_sizes.py -v

install:
	./install.sh

setup:
	./install.sh

serve:
	python3 -m hermesbench serve $(MODEL) --port $(PORT)

run-all:
	python3 -m hermesbench run --all --model $(MODEL) --base-url $(BASE_URL)

clean:
	rm -rf traces/*/*/worktree/ results/*/*/worktree/ __pycache__/
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
