.PHONY: run
run:
	python3 scraping.py 2>&1

.PHONY: lint
lint:
	flake8
