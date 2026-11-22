.PHONY: help run book test

help:
	@printf 'Commands:\n  make run   Set up and run the shipping agent\n  make book  Set up and run the booking agent\n  make test  Run the test suite\n'

test:
	uv run --locked --extra test python -m unittest discover -s tests -v

run:
	uv sync --locked
	uv run --locked python -m examples.shipping.launch

book:
	uv sync --locked
	uv run --locked python -m examples.shipping.launch --book
