.PHONY: run
run:
	python3 scraping.py 2>&1

.PHONY: lint
lint:
	flake8

.PHONY: profile
profile:
	python3 -m cProfile scraping.py 2>&1
