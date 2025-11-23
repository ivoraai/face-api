# Docker Setup Guide

This project is fully dockerized with multi-stage builds for optimal performance. The setup includes:

- **FastAPI Service** - Face extraction, clustering, and search with RetinaFace + ArcFace
- **Qdrant Database** - Vector database for face embeddings
- **Redis** (Optional) - For Celery background tasks

## Prerequisites

- Docker & Docker Compose installed
- At least 8GB RAM available
- 10GB+ disk space (for model downloads and Qdrant storage)

## Quick Start

### 1. Build and Run with Docker Compose

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f face-api
```

The API will be available at: **http://localhost:8000**
Qdrant Dashboard: **http://localhost:6333/dashboard**

### 2. Build the Image Manually

```bash
# Build the image
docker build -t face-embedding-api:latest .

# Run with Docker Compose
docker-compose up -d

# Or run standalone
docker run -p 8000:8000 \
  -e QDRANT_URL=qdrant \
  -e QDRANT_PORT=6333 \
  --network face-network \
  face-embedding-api:latest
```

## Configuration

### Environment Variables

Create or modify `.env` file:

```bash
# Copy the template
cp .env.docker .env

# Edit as needed
QDRANT_URL=qdrant
QDRANT_PORT=6333
QDRANT_API_KEY=your-secret-key
QDRANT_COLLECTION=face_embeddings
EMBEDDING_SIZE=512
```

### Using Celery with Redis

To enable background job queuing:

```bash
# Include Redis service (default is excluded)
docker-compose --profile celery up -d

# Set environment variables
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

## API Usage Examples

### 1. Check Health

```bash
curl http://localhost:8000/
```

### 2. Extract Faces from Image

```bash
curl -X POST http://localhost:8000/get-faces \
  -F "file=@image.jpg"
```

### 3. Start Digestion Job

```bash
curl -X POST http://localhost:8000/digest \
  -H "Content-Type: application/json" \
  -d '{"group_id":"photos"}'
```

### 4. Cluster Faces

```bash
curl -X POST http://localhost:8000/cluster-faces \
  -H "Content-Type: application/json" \
  -d '{"group_id":"photos","confidence":0.85}'
```

### 5. Monitor Cluster Jobs

```bash
curl http://localhost:8000/get-clusters
curl http://localhost:8000/get-clusters/{job_id}
```

## Docker Compose Services

### face-api

- **Image**: Built from Dockerfile (local)
- **Port**: 8000
- **Volumes**:
  - `./data:/app/data` - Data directory
  - `./logs:/app/logs` - Logs
  - `./thumbnails:/app/thumbnails` - Face thumbnails
- **Depends on**: Qdrant (with health check)

### qdrant

- **Image**: qdrant/qdrant:v1.11.0
- **Port**: 6333 (gRPC), 6334 (REST)
- **Volumes**: Persistent storage for vector data
- **Health check**: Enabled

### redis (Optional - Celery Profile)

- **Image**: redis:7-alpine
- **Port**: 6379
- **Profile**: celery (activate with `--profile celery`)

## Building with Model Caching

The Dockerfile uses multi-stage builds to:

1. **Builder Stage**: Downloads and caches RetinaFace & ArcFace models during build
2. **Final Stage**: Only includes runtime dependencies and cached models

This ensures:
- ✅ Models are pre-downloaded and cached in the image
- ✅ No network access needed at runtime
- ✅ Faster startup times
- ✅ Smaller final image size

## Volume Mounts

```yaml
volumes:
  - ./data:/app/data              # Persistent data
  - ./logs:/app/logs              # Application logs
  - ./thumbnails:/app/thumbnails  # Generated thumbnails
  - qdrant_data:/qdrant/storage   # Qdrant vectors
  - redis_data:/data              # Redis persistence (if using)
```

## Common Commands

### Start Services

```bash
# All services
docker-compose up -d

# Specific service
docker-compose up -d face-api

# With Celery/Redis
docker-compose --profile celery up -d
```

### Stop Services

```bash
docker-compose down
```

### Remove Everything (including volumes)

```bash
docker-compose down -v
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f face-api
docker-compose logs -f qdrant

# Last 100 lines
docker-compose logs --tail=100 face-api
```

### Rebuild Image

```bash
docker-compose build --no-cache face-api
```

### Enter Container Shell

```bash
docker-compose exec face-api bash
docker-compose exec qdrant bash
```

### Check Health

```bash
# API
curl http://localhost:8000/health 2>/dev/null || echo "Not healthy"

# Qdrant
curl http://localhost:6333/health
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs face-api

# Rebuild without cache
docker-compose build --no-cache face-api
docker-compose up -d
```

### Out of Memory

Increase Docker memory limit or check model cache:

```bash
# Clear Docker cache
docker system prune -a

# Rebuild
docker-compose build --no-cache
```

### Qdrant Connection Error

```bash
# Verify Qdrant is running
docker-compose ps

# Check Qdrant logs
docker-compose logs qdrant

# Restart Qdrant
docker-compose restart qdrant
```

### Port Already in Use

Change ports in `docker-compose.yml`:

```yaml
services:
  face-api:
    ports:
      - "8001:8000"  # Map to different host port
  qdrant:
    ports:
      - "6334:6333"
```

## Production Deployment

### Environment Setup

1. Use strong API keys:
```bash
QDRANT_API_KEY=your-very-strong-secret-key
```

2. Configure resource limits:
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

3. Use external Qdrant instance (optional):
```bash
QDRANT_URL=qdrant.example.com
QDRANT_PORT=6333
QDRANT_API_KEY=production-key
```

### Persistence

Ensure volumes are on reliable storage:

```yaml
volumes:
  qdrant_data:
    driver: local
    driver_opts:
      type: nfs
      o: addr=nfs.example.com,vers=4,soft,timeo=180,bg,tcp,rw
      device: ":/export/qdrant"
```

### Monitoring

Add monitoring stack (Prometheus + Grafana):

```bash
docker-compose --profile monitoring up -d
```

## Image Information

- **Base Image**: python:3.11-slim (lightweight)
- **Final Size**: ~2GB (includes all ML models)
- **Build Time**: ~15-20 minutes (first build, includes model downloads)
- **Runtime Memory**: 2-4GB typical usage

### Pre-installed Models

During Docker build, these models are cached:

- **RetinaFace** - Face detection model
- **ArcFace** - Face embedding/recognition model
- **TensorFlow/Keras** - Deep learning framework

## Performance Tips

1. **Use BuildKit for faster builds**:
   ```bash
   DOCKER_BUILDKIT=1 docker-compose build
   ```

2. **Increase Docker memory**:
   - Docker Desktop: Settings → Resources → Memory (increase to 4GB+)

3. **Use volume mounts for large datasets**:
   ```bash
   docker run -v /path/to/data:/app/data face-embedding-api
   ```

4. **Enable Swap**:
   ```bash
   docker run --memory=4g --memory-swap=6g face-embedding-api
   ```

## Network Modes

### Bridge Network (Default)

Services communicate via service names:
```
face-api → qdrant:6333
```

### Host Network

For maximum performance on Linux:

```yaml
services:
  face-api:
    network_mode: host
```

### Custom Network

Already configured in `docker-compose.yml`:

```yaml
networks:
  face-network:
    driver: bridge
```

## Cleanup

```bash
# Stop all services
docker-compose down

# Remove volumes (data loss!)
docker-compose down -v

# Remove images
docker rmi face-embedding-api:latest
docker rmi qdrant/qdrant:v1.11.0

# Full cleanup
docker system prune -a --volumes
```

## Getting Help

1. Check container logs: `docker-compose logs -f`
2. Verify services are running: `docker-compose ps`
3. Test API endpoint: `curl http://localhost:8000/`
4. Inspect network: `docker network inspect face-network`

