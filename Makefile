all: install run

install:
	uv pip install -r requirements.txt

run:
	uvicorn app:app --host 0.0.0.0 --port 8000

.PHONY: all install run