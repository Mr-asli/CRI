.PHONY: up down test coverage audit e2e kill reset dashboard-install dashboard-test dashboard-build clean

up:
	docker compose up --build -d
	docker compose ps

down:
	docker compose down --remove-orphans

test:
	python -m pytest -q

coverage:
	python -m coverage run --source=backend/cri -m pytest -q
	python -m coverage report -m --fail-under=85

audit:
	./scripts/verify-audit.sh

e2e:
	./scripts/run-e2e-demo.sh

kill:
	./scripts/run-kill-switch-test.sh

reset:
	docker compose down --volumes --remove-orphans

dashboard-install:
	cd dashboard && npm install --no-audit --no-fund

dashboard-test:
	cd dashboard && npm test -- --run

dashboard-build:
	cd dashboard && npm run lint && npm run build

clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
	rm -rf dashboard/dist dashboard/coverage .coverage htmlcov
