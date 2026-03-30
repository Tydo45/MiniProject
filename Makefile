.PHONY: dev down logs deploy

dev:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f

deploy:
	./k8s/deploy.sh