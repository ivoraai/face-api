# Docker Deployment Guide

Complete containerization of the Face Embedding API with RetinaFace and ArcFace.

## 📋 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Usage](#api-usage)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)

## Overview

### What's Included

- **FastAPI Application** - Face detection, embedding, clustering, search
- **Qdrant Vector DB** - Persistent vector storage for embeddings
- **Docker Compose** - Multi-service orchestration
- **Pre-installed Models**:
  - RetinaFace (face detection)
  - ArcFace (face embeddings/recognition)
  - TensorFlow/Keras framework

### Architecture

```
┌─────────────────────────────────────────────┐
│            External Client                   │
└────────────────────┬────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │   FastAPI Service      │
        │   (Port 8000)          │
        │ - Face Detection       │
        │ - Face Embeddings      │
        │ - Clustering           │
        │ - Search               │
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │   Qdrant Database      │
        │   (Port 6333)          │
        │ - Vector Storage       │
        │ - Similarity Search    │
        └────────────────────────┘
        
Optional:
        ┌────────────────────────┐
        │   Redis Cache          │
        │   (Port 6379)          │
        │ - Background Jobs      │
        └────────────────────────┘
```

## Quick Start

### 1. Prerequisites

```bash
# Check Docker and Docker Compose installation
docker --version
docker-compose --version

# Ensure adequate resources
# - 8GB+ RAM
# - 10GB+ disk space
# - Ports 8000, 6333 available
```

### 2. Clone and Setup

```bash
cd /Users/harshitsmac/Documents/dr

# Copy environment template
cp .env.docker .env

# View configuration
cat .env
```

### 3. Build and Start

```bash
# Build the image (first time, ~15-20 minutes)
docker-compose build

# Start services
docker-compose up -d

# Verify services are running
docker-compose ps

# Check health
curl http://localhost:8000/
```

### 4. Test the API

```bash
# List all services
docker-compose ps

# View logs
docker-compose logs -f face-api

# Test endpoints
curl http://localhost:8000/get-clusters
curl http://localhost:8000/get-digests
```

### 5. Stop Services

```bash
# Stop without removing volumes (data persists)
docker-compose down

# Stop and remove volumes (DELETES DATA)
docker-compose down -v

# Remove images
docker system prune -a
```

## Configuration

### Environment Variables

Edit `.env` file:

```bash
# Qdrant Settings
QDRANT_URL=qdrant                    # Service name or IP
QDRANT_PORT=6333                     # Qdrant port
QDRANT_API_KEY=                      # Optional API key
QDRANT_COLLECTION=face_embeddings    # Collection name

# Embedding Settings
EMBEDDING_SIZE=512                   # Embedding dimension

# Optional: Celery Background Jobs
# CELERY_BROKER_URL=redis://redis:6379/0
# CELERY_RESULT_BACKEND=redis://redis:6379/0
```

### Resource Limits

Edit `docker-compose.yml`:

```yaml
services:
  face-api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### Volume Mounting

Default mounts:

```yaml
volumes:
  - ./data:/app/data                 # Data directory
  - ./logs:/app/logs                 # Application logs
  - ./thumbnails:/app/thumbnails     # Face thumbnails
```

Mount additional directories:

```bash
# Create local directories
mkdir -p /path/to/data /path/to/logs

# Update docker-compose.yml
volumes:
  - /path/to/data:/app/data
  - /path/to/logs:/app/logs
```

## API Usage

### Health Check

```bash
curl http://localhost:8000/
# Response: {"status": "ok"}
```

### Extract Faces

```bash
curl -X POST http://localhost:8000/get-faces \
  -F "file=@photo.jpg"

# Response:
# {
#   "status": "success",
#   "faces": [...],
#   "count": 3
# }
```

### Digest Images (Background Job)

```bash
curl -X POST http://localhost:8000/digest \
  -H "Content-Type: application/json" \
  -d '{
    "group_id": "family_photos",
    "directory": "media_service/",
    "batch_size": 50
  }'

# Response: {"job_id": "digest-uuid-..."}
```

### Monitor Digest Jobs

```bash
# List all digest jobs
curl http://localhost:8000/get-digests

# Get specific job
curl http://localhost:8000/get-digests/{job_id}
```

### Cluster Faces

```bash
curl -X POST http://localhost:8000/cluster-faces \
  -H "Content-Type: application/json" \
  -d '{
    "group_id": "family_photos",
    "confidence": 0.85
  }'

# Response: {"job_id": "cluster-uuid-..."}
```

### Monitor Cluster Jobs

```bash
# List all cluster jobs
curl http://localhost:8000/get-clusters

# Get specific job
curl http://localhost:8000/get-clusters/{job_id}
```

### Search Faces

```bash
curl -X POST http://localhost:8000/search-face \
  -F "file=@query.jpg" \
  -F "top_k=5"

# Response:
# {
#   "matches": [...],
#   "query_embedding": [...]
# }
```

## Docker Commands Reference

### Build

```bash
# Build with default Dockerfile
docker-compose build

# Build with production Dockerfile
docker-compose build -f docker-compose.prod.yml

# Build without cache
docker-compose build --no-cache

# Build specific service
docker-compose build face-api
```

### Run

```bash
# Start all services (detached)
docker-compose up -d

# Start specific service
docker-compose up -d face-api

# Start with Celery/Redis
docker-compose --profile celery up -d

# Start with production config
docker-compose -f docker-compose.prod.yml up -d
```

### Manage

```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f                    # All services
docker-compose logs -f face-api           # Specific service
docker-compose logs --tail=100 qdrant     # Last 100 lines

# Enter container shell
docker-compose exec face-api bash
docker-compose exec qdrant sh

# Stop services
docker-compose stop
docker-compose stop face-api              # Stop specific service

# Restart services
docker-compose restart
docker-compose restart qdrant

# Remove services
docker-compose down                       # Stop and remove
docker-compose down -v                    # Also remove volumes
docker-compose down --rmi all             # Also remove images
```

### Advanced

```bash
# Check service dependencies
docker-compose config

# Validate configuration
docker-compose config --quiet

# Execute command in service
docker-compose exec face-api python -c "import deepface; print('OK')"

# Inspect network
docker network inspect face-network

# View resource usage
docker stats

# Copy files to/from container
docker cp container:/path/file ./local/path
docker cp ./local/file container:/path/file
```

## Production Deployment

### Use Production Image

```bash
# Build production image
docker-compose -f docker-compose.prod.yml build

# Start production services
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps
```

### Key Production Features

✅ **Security**:
- Non-root user (appuser)
- Restricted file permissions
- Security headers in nginx
- API key authentication (Qdrant)

✅ **Performance**:
- Multi-worker uvicorn
- Resource limits set
- Health checks enabled
- Graceful shutdown

✅ **Reliability**:
- Restart always policy
- Health monitoring
- Persistent volumes
- Error logging

### Setup SSL/HTTPS

Create `nginx.conf`:

```nginx
upstream api {
    server face-api:8000;
}

server {
    listen 443 ssl;
    server_name api.example.com;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    location / {
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name api.example.com;
    return 301 https://$server_name$request_uri;
}
```

Start nginx:

```bash
docker-compose -f docker-compose.prod.yml --profile proxy up -d
```

### Monitor with Docker Stats

```bash
# Real-time resource monitoring
docker stats

# Watch specific container
docker stats face-api
```

### Backup Volumes

```bash
# Backup Qdrant data
docker run --rm \
  -v qdrant_data:/data \
  -v /path/to/backup:/backup \
  busybox tar czf /backup/qdrant_backup.tar.gz -C /data .

# Restore from backup
docker run --rm \
  -v qdrant_data:/data \
  -v /path/to/backup:/backup \
  busybox tar xzf /backup/qdrant_backup.tar.gz -C /data
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs face-api

# Rebuild without cache
docker-compose build --no-cache face-api
docker-compose up -d face-api

# Check resource availability
docker stats
```

### API not responding

```bash
# Check if container is running
docker-compose ps

# Check API logs
docker-compose logs -f face-api

# Test connectivity
curl -v http://localhost:8000/

# Restart service
docker-compose restart face-api
```

### Qdrant connection error

```bash
# Verify Qdrant is running
docker-compose ps qdrant

# Check Qdrant logs
docker-compose logs qdrant

# Test Qdrant directly
curl http://localhost:6333/health

# Restart and check
docker-compose restart qdrant
sleep 5
curl http://localhost:6333/health
```

### Out of memory

```bash
# Check Docker memory allocation
docker info | grep Memory

# Increase Docker memory (Docker Desktop)
# Settings → Resources → Memory: increase to 4GB+

# Check container memory usage
docker stats

# Clear cache
docker system prune -a
```

### Port already in use

```bash
# Find what's using the port
lsof -i :8000
lsof -i :6333

# Change ports in docker-compose.yml
# Or kill existing process
kill -9 <PID>
```

### Models not downloading

```bash
# Check internet connection
curl https://github.com

# Rebuild with extended timeout
docker-compose build --no-cache

# Pre-download manually
docker-compose exec face-api python -c "
from deepface import DeepFace
import numpy as np
DeepFace.extract_faces(np.ones((100,100,3), dtype=np.uint8), detector_backend='retinaface')
"
```

### Database corruption

```bash
# Backup data
docker cp face-qdrant:/qdrant/storage ./qdrant_backup

# Reset database (DELETES DATA)
docker-compose down -v
docker-compose up -d

# Restore from backup
docker cp ./qdrant_backup face-qdrant:/qdrant/storage
docker-compose restart qdrant
```

## Performance Tips

### 1. Use BuildKit for Faster Builds

```bash
export DOCKER_BUILDKIT=1
docker-compose build
```

### 2. Increase Docker Resources

```bash
# Docker Desktop: Settings → Resources
# CPU: 4+
# Memory: 8GB+
# Swap: 4GB+
```

### 3. Use Volume Mounts for Data

```yaml
volumes:
  - /fast/ssd/path:/app/data  # Fast storage
  - /network/storage:/app/backup  # Network backup
```

### 4. Enable Caching

```bash
# Build with cache
docker-compose build --cache-from face-embedding-api:latest

# Use pre-built images from registry
docker pull myregistry.com/face-embedding-api:latest
```

### 5. Optimize Qdrant

```yaml
environment:
  - QDRANT_SEARCH_BATCH_SIZE=1000
  - QDRANT_SNAPSHOTS_COMPRESSION_TYPE=gzip
```

## Scaling

### Horizontal Scaling

Use Docker Swarm or Kubernetes:

```bash
# Initialize Docker Swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.prod.yml face-api

# Scale service
docker service scale face-api=3
```

### Vertical Scaling

Increase resource limits:

```yaml
deploy:
  resources:
    limits:
      cpus: '8'
      memory: 16G
```

### Load Balancing

Use Nginx or HAProxy for multiple instances:

```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx_lb.conf:/etc/nginx/nginx.conf
    depends_on:
      - face-api-1
      - face-api-2
      - face-api-3
```

## Security Considerations

### 1. Use Strong API Keys

```bash
# Generate secure key
openssl rand -base64 32
# Set in .env
QDRANT_API_KEY=your-strong-key
```

### 2. Network Isolation

```yaml
networks:
  face-network:
    driver: bridge
    # Restrict external access
```

### 3. Use Private Registry

```bash
# Tag image
docker tag face-embedding-api:latest myregistry.com/face-embedding-api:latest

# Push to private registry
docker push myregistry.com/face-embedding-api:latest

# Pull from registry
docker pull myregistry.com/face-embedding-api:latest
```

### 4. Enable HTTPS

Use nginx proxy with SSL certificates.

### 5. Limit Resource Access

```yaml
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 8G
    reservations:
      cpus: '2'
      memory: 4G
```

## Getting Help

```bash
# Check Docker logs
docker-compose logs -f

# Verify configuration
docker-compose config

# Run in interactive mode
docker-compose run --rm face-api bash

# Test individual services
docker-compose exec qdrant curl http://localhost:6333/health
docker-compose exec face-api python -c "import deepface; print('OK')"
```

