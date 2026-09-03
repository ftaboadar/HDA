.PHONY: up down test report local-run gcp-check gcp-plan gcp-apply gcp-destroy

up:
	docker compose up -d --build

down:
	docker compose down -v

test:
	pip install -q -r requirements-dev.txt
	pytest tests/ -v

report:
	python tests/reporte.py

local-run: up
	@echo "Esperando a que los servicios estén sanos..."
	@for i in $$(seq 1 30); do \
		curl -sf http://localhost:8000/salud > /dev/null && break; \
		sleep 2; \
	done
	$(MAKE) test
	$(MAKE) report

gcp-check:
	python -m cli.hda_gcp.main check

gcp-plan:
	python -m cli.hda_gcp.main infra plan --project $(PROJECT)

gcp-apply:
	python -m cli.hda_gcp.main infra apply --project $(PROJECT)

gcp-destroy:
	python -m cli.hda_gcp.main infra destroy --project $(PROJECT)
