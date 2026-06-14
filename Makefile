.PHONY: build run results airflow down psql

build:        ## Build the pipeline image
	docker compose build

run:          ## Run the full pipeline (extract -> load -> dbt -> results)
	docker compose run --rm pipeline run-all

results:      ## Print the two business answers
	docker compose run --rm pipeline show-results

airflow:      ## Start Airflow UI (http://localhost:8080, admin/admin)
	docker compose --profile airflow up -d

psql:         ## Open a psql shell on the warehouse
	docker compose exec postgres psql -U warehouse -d warehouse

down:         ## Stop everything and remove volumes
	docker compose --profile airflow down -v
