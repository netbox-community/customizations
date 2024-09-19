
VERSION := $(shell git describe --tags --always --dirty="-dev")
PROJECT_ROOT := .

BLACK_EXLCUDE := ".venv"

.PHONY: clean pyvenv format ruff-fix lint coverage

clean:
	rm -rf $(PROJECT_ROOT)/.cover/

pyvenv:
	python3 -m venv .venv
	./.venv/bin/pip install -r dev-testing-requirements.txt

format:
	./.venv/bin/python -m black --exclude $(BLACK_EXLCUDE) ./

ruff-fix:
	./.venv/bin/python -m ruff check ./ --fix

lint: pyvenv
	./.venv/bin/python -m ruff check ./
	./.venv/bin/python -m black --exclude $(BLACK_EXLCUDE) ./ --check

coverage:
	mkdir -p $(PROJECT_ROOT)/.cover/
	chmod 0777 $(PROJECT_ROOT)/.cover/
	docker-compose -f docker-compose.test.yml up --exit-code-from netbox --abort-on-container-exit
	docker cp netbox_test:/tmp/.cover ./$(PROJECT_ROOT)/
	open $(PROJECT_ROOT)/.cover/index.html
