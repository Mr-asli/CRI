.PHONY: up test audit e2e kill reset

up:
	docker compose up --build -d
	docker compose ps

test:
	PYTHONPATH=backend pytest -q

audit:
	./scripts/verify-audit.sh

e2e:
	./scripts/run-e2e-demo.sh

kill:
	./scripts/run-kill-switch-test.sh

reset:
	docker compose down --volumes --remove-orphans
