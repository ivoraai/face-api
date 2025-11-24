.PHONY: help install start dev stop restart logs clean test docker-build docker-up docker-down deploy-appengine deploy-cloudrun

# Variables
PYTHON := python3
PIP := $(PYTHON) -m pip
UVICORN := uvicorn
APP_MODULE := face_service_fastapi:app
HOST := 0.0.0.0
PORT := 8000

# GCP Deployment Variables
GCP_PROJECT := image-478813
GCP_REGION := asia-southeast1
DOCKER_IMAGE := asia-southeast1-docker.pkg.dev/image-478813/a1-moments/face-api:latest
CLOUD_RUN_SERVICE := face-api
APPENGINE_SERVICE := default

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

help: ## Show this help message
	@echo "$(GREEN)Available commands:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

install: ## Install Python dependencies
	@echo "$(GREEN)Installing dependencies...$(NC)"
	uv pip install -r requirements.txt || $(PIP) install -r requirements.txt
	@echo "$(GREEN)Dependencies installed!$(NC)"

start: ## Start the FastAPI service (production mode)
	@echo "$(GREEN)Starting Face Worker Service on http://$(HOST):$(PORT)$(NC)"
	$(UVICORN) $(APP_MODULE) --host $(HOST) --port $(PORT)

dev: ## Start the service in development mode with auto-reload
	@echo "$(GREEN)Starting Face Worker Service in development mode...$(NC)"
	$(UVICORN) $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

dev-logs: ## Start with detailed logging
	@echo "$(GREEN)Starting with detailed logs...$(NC)"
	$(UVICORN) $(APP_MODULE) --host $(HOST) --port $(PORT) --reload --log-level debug

docker-build: ## Build Docker image
	@echo "$(GREEN)Building Docker image...$(NC)"
	docker-compose build

docker-up: ## Start services with Docker Compose
	@echo "$(GREEN)Starting services with Docker Compose...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)Services started! Check logs with 'make docker-logs'$(NC)"

docker-up-build: ## Build and start services
	@echo "$(GREEN)Building and starting services...$(NC)"
	docker-compose up -d --build

docker-down: ## Stop Docker containers
	@echo "$(YELLOW)Stopping Docker services...$(NC)"
	docker-compose down

docker-logs: ## Show Docker container logs
	docker-compose logs -f

docker-shell: ## Open shell in container
	docker-compose exec face-service bash

clean: ## Clean up Python cache
	@echo "$(YELLOW)Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "$(GREEN)Cleanup complete!$(NC)"

test-api: ## Test API health
	@echo "$(GREEN)Testing API health...$(NC)"
	@curl -s http://localhost:$(PORT)/ | $(PYTHON) -m json.tool || echo "$(RED)API not responding$(NC)"

test-copy-drive: ## Test copy-drive-to-gcs endpoint
	@echo "$(GREEN)Testing copy-drive-to-gcs...$(NC)"
	@if [ -z "$(DRIVE_LINK)" ] || [ -z "$(GCS_BUCKET)" ]; then \
		echo "$(RED)Usage: make test-copy-drive DRIVE_LINK='https://...' GCS_BUCKET='bucket' GCS_DIR='dir'$(NC)"; \
		exit 1; \
	fi
	curl -X POST http://localhost:$(PORT)/copy-drive-to-gcs \
		-H "Content-Type: application/json" \
		-d '{"drive_link": "$(DRIVE_LINK)", "gcs_bucket": "$(GCS_BUCKET)", "gcs_directory": "$(GCS_DIR)"}'

test-digest: ## Test digest endpoint
	@echo "$(GREEN)Testing digest...$(NC)"
	@if [ -z "$(GCS_BUCKET)" ] || [ -z "$(GROUP_ID)" ]; then \
		echo "$(RED)Usage: make test-digest GCS_BUCKET='bucket' GROUP_ID='id' GCS_PREFIX='prefix/'$(NC)"; \
		exit 1; \
	fi
	curl -X POST http://localhost:$(PORT)/digest \
		-H "Content-Type: application/json" \
		-d '{"gcs_bucket": "$(GCS_BUCKET)", "gcs_prefix": "$(GCS_PREFIX)", "group_id": "$(GROUP_ID)", "threads": 4}'

check-jobs: ## Check all job statuses
	@curl -s http://localhost:$(PORT)/get-digests | $(PYTHON) -m json.tool

check-job: ## Check specific job (requires JOB_ID)
	@if [ -z "$(JOB_ID)" ]; then \
		echo "$(RED)Usage: make check-job JOB_ID='copy-drive-abc123'$(NC)"; \
		exit 1; \
	fi
	@curl -s http://localhost:$(PORT)/get-digests/$(JOB_ID) | $(PYTHON) -m json.tool

check-env: ## Check environment setup
	@echo "$(GREEN)Checking environment...$(NC)"
	@[ -f "sa.json" ] && echo "$(GREEN)✓ sa.json found$(NC)" || echo "$(RED)✗ sa.json missing$(NC)"
	@[ -f ".env" ] && echo "$(GREEN)✓ .env found$(NC)" || echo "$(YELLOW)⚠ .env missing$(NC)"

# ============================================
# GCP Deployment Commands
# ============================================

gcp-config: ## Configure GCP project
	@echo "$(GREEN)Setting GCP project...$(NC)"
	gcloud config set project $(GCP_PROJECT)
	@echo "$(GREEN)GCP project set to: $(GCP_PROJECT)$(NC)"

deploy-cloudrun: ## Deploy to Cloud Run (Recommended for Docker)
	@echo "$(GREEN)Deploying to Cloud Run...$(NC)"
	gcloud run deploy $(CLOUD_RUN_SERVICE) \
		--image=$(DOCKER_IMAGE) \
		--platform=managed \
		--region=$(GCP_REGION) \
		--project=$(GCP_PROJECT) \
		--allow-unauthenticated \
		--memory=4Gi \
		--cpu=2 \
		--timeout=3600 \
		--max-instances=10 \
		--set-env-vars="QDRANT_URL=localhost,QDRANT_PORT=6333,EMBEDDING_SIZE=512" \
		--service-account=face-api@$(GCP_PROJECT).iam.gserviceaccount.com
	@echo "$(GREEN)Deployment complete!$(NC)"
	@echo "$(YELLOW)Get service URL:$(NC) make cloudrun-url"

deploy-cloudrun-with-secrets: ## Deploy Cloud Run with secrets
	@echo "$(GREEN)Deploying to Cloud Run with secrets...$(NC)"
	gcloud run deploy $(CLOUD_RUN_SERVICE) \
		--image=$(DOCKER_IMAGE) \
		--platform=managed \
		--region=$(GCP_REGION) \
		--project=$(GCP_PROJECT) \
		--allow-unauthenticated \
		--memory=4Gi \
		--cpu=2 \
		--timeout=3600 \
		--max-instances=10 \
		--set-secrets="QDRANT_API_KEY=qdrant-api-key:latest" \
		--set-env-vars="QDRANT_URL=your-qdrant-url,QDRANT_PORT=6333,EMBEDDING_SIZE=512"
	@echo "$(GREEN)Deployment complete!$(NC)"

deploy-appengine: ## Deploy to App Engine Flexible
	@echo "$(GREEN)Deploying to App Engine Flexible...$(NC)"
	@if [ ! -f "app.yaml" ]; then \
		echo "$(RED)Error: app.yaml not found. Run 'make create-appengine-config' first$(NC)"; \
		exit 1; \
	fi
	gcloud app deploy app.yaml \
		--project=$(GCP_PROJECT) \
		--image-url=$(DOCKER_IMAGE) \
		--quiet
	@echo "$(GREEN)Deployment complete!$(NC)"
	@echo "$(YELLOW)View app:$(NC) make appengine-browse"

create-appengine-config: ## Create app.yaml for App Engine
	@echo "$(GREEN)Creating app.yaml...$(NC)"
	@echo "runtime: custom" > app.yaml
	@echo "env: flex" >> app.yaml
	@echo "" >> app.yaml
	@echo "service: $(APPENGINE_SERVICE)" >> app.yaml
	@echo "" >> app.yaml
	@echo "manual_scaling:" >> app.yaml
	@echo "  instances: 1" >> app.yaml
	@echo "" >> app.yaml
	@echo "resources:" >> app.yaml
	@echo "  cpu: 2" >> app.yaml
	@echo "  memory_gb: 4" >> app.yaml
	@echo "  disk_size_gb: 10" >> app.yaml
	@echo "" >> app.yaml
	@echo "env_variables:" >> app.yaml
	@echo "  QDRANT_URL: 'localhost'" >> app.yaml
	@echo "  QDRANT_PORT: '6333'" >> app.yaml
	@echo "  EMBEDDING_SIZE: '512'" >> app.yaml
	@echo "$(GREEN)app.yaml created successfully!$(NC)"

cloudrun-url: ## Get Cloud Run service URL
	@gcloud run services describe $(CLOUD_RUN_SERVICE) \
		--region=$(GCP_REGION) \
		--project=$(GCP_PROJECT) \
		--format='value(status.url)'

cloudrun-logs: ## View Cloud Run logs
	@echo "$(GREEN)Viewing Cloud Run logs...$(NC)"
	gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$(CLOUD_RUN_SERVICE)" \
		--project=$(GCP_PROJECT) \
		--limit=50 \
		--format=json

cloudrun-tail-logs: ## Tail Cloud Run logs in real-time
	@echo "$(GREEN)Tailing Cloud Run logs...$(NC)"
	gcloud alpha run services logs tail $(CLOUD_RUN_SERVICE) \
		--region=$(GCP_REGION) \
		--project=$(GCP_PROJECT)

cloudrun-delete: ## Delete Cloud Run service
	@echo "$(YELLOW)Deleting Cloud Run service...$(NC)"
	gcloud run services delete $(CLOUD_RUN_SERVICE) \
		--region=$(GCP_REGION) \
		--project=$(GCP_PROJECT) \
		--quiet
	@echo "$(GREEN)Service deleted$(NC)"

appengine-browse: ## Open App Engine app in browser
	gcloud app browse --project=$(GCP_PROJECT)

appengine-logs: ## View App Engine logs
	gcloud app logs tail --project=$(GCP_PROJECT)

appengine-versions: ## List App Engine versions
	gcloud app versions list --project=$(GCP_PROJECT)

docker-push: ## Push Docker image to Artifact Registry
	@echo "$(GREEN)Pushing Docker image...$(NC)"
	docker push $(DOCKER_IMAGE)
	@echo "$(GREEN)Image pushed successfully!$(NC)"

docker-build-and-push: ## Build and push Docker image
	@echo "$(GREEN)Building Docker image...$(NC)"
	docker build -t $(DOCKER_IMAGE) .
	@echo "$(GREEN)Pushing to Artifact Registry...$(NC)"
	docker push $(DOCKER_IMAGE)
	@echo "$(GREEN)Build and push complete!$(NC)"

gcp-authenticate: ## Authenticate with GCP (user account)
	@echo "$(GREEN)Authenticating with GCP...$(NC)"
	gcloud auth login
	gcloud config set project $(GCP_PROJECT)
	gcloud auth configure-docker $(GCP_REGION)-docker.pkg.dev

gcp-auth-sa: ## Authenticate with service account (sa.json)
	@echo "$(GREEN)Authenticating with service account...$(NC)"
	@if [ ! -f "sa.json" ]; then \
		echo "$(RED)Error: sa.json not found$(NC)"; \
		exit 1; \
	fi
	gcloud auth activate-service-account --key-file=sa.json
	gcloud config set project $(GCP_PROJECT)
	gcloud auth configure-docker $(GCP_REGION)-docker.pkg.dev
	@echo "$(GREEN)Service account authenticated!$(NC)"

enable-appengine: ## Enable App Engine API
	@echo "$(GREEN)Enabling App Engine API...$(NC)"
	gcloud services enable appengine.googleapis.com --project=$(GCP_PROJECT)
	@echo "$(GREEN)App Engine API enabled!$(NC)"

create-appengine-app: ## Create App Engine app (first time only)
	@echo "$(GREEN)Creating App Engine app...$(NC)"
	gcloud app create --region=$(GCP_REGION) --project=$(GCP_PROJECT)
	@echo "$(GREEN)App Engine app created!$(NC)"

deploy-quick: gcp-config deploy-cloudrun cloudrun-url ## Quick deploy to Cloud Run

.DEFAULT_GOAL := help