ifneq ("$(wildcard .env)","")
include .env
endif


SOURCES_DIR = "."


.PHONY: env
env:
	poetry install

# TODO: [2024-07-20 by Mykola] Enable style checks.
#.PHONY: style
#style:
#	poetry run black $(SOURCES_DIR)
#	poetry run isort $(SOURCES_DIR)
#	poetry run pylint $(SOURCES_DIR)
#	poetry run pydocstyle $(SOURCES_DIR)

# TODO: [2024-07-20 by Mykola] Enable docs generation.
#.PHONY: docs
#docs:
#	sphinx-apidoc --force --append-syspath --output-dir ./docs/source $(SOURCES_DIR)
#	cd docs && $(MAKE) html

.PHONY: migrate
migrate:
	poetry run aerich upgrade


# TODO: [2024-07-20 by Mykola] Use `$(SOURCES_DIR)` instead of `.` in the commands below.

.PHONY: extract-locales
extract-locales:
	poetry run pybabel --quiet extract --input-dirs . --output ./locales/messages.pot

.PHONY: locales
locales:
	$(MAKE) extract-locales
	poetry run pybabel update --input-file ./locales/messages.pot --output-dir ./locales/

.PHONY: compile-locales
compile-locales:
	poetry run pybabel compile -f --directory ./locales/

# endregion


.PHONY: pre-start
pre-start:
	${MAKE} migrate
	${MAKE} compile-locales

.PHONY: start
start:
	poetry run python ./test_flow.py