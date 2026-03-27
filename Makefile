.PHONY: dev down logs

dev:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f