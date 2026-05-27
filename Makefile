VENV_DIR := venv
PYTHON := python3
PIP := $(VENV_DIR)/bin/pip
PYTEST := $(VENV_DIR)/bin/pytest
COVERAGE := $(VENV_DIR)/bin/coverage

.PHONY: venv test test-html clean clean-all

venv: $(VENV_DIR)/bin/activate

$(VENV_DIR)/bin/activate: requirements.txt
	$(PYTHON) -m venv $(VENV_DIR)
	$(PIP) install --upgrade pip
	$(PIP) install pytest pytest-cov
	touch $(VENV_DIR)/bin/activate

test: venv
	$(PYTEST) tests/ \
		--cov=vinylstudio_to_jb7 \
		--cov-report=term-missing \
		--cov-fail-under=90 \
		-vv

test-html: venv
	$(PYTEST) tests/ \
		--cov=vinylstudio_to_jb7 \
		--cov-report=html \
		--cov-report=term-missing \
		--cov-fail-under=90 \
		-vv
	@echo "HTML coverage report: file://$(PWD)/htmlcov/index.html"

clean:
	rm -rf $(VENV_DIR)
	rm -rf __pycache__ */__pycache__ */*/__pycache__
	rm -rf .pytest_cache
	rm -rf .coverage htmlcov
	rm -rf *.egg-info
	rm -rf dist build
	find . -name '*.pyc' -delete
	find . -name '*.pyo' -delete
