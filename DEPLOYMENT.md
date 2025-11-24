# Deployment Guide

This guide covers deploying the Face Recognition API to Google Cloud Platform.

## Prerequisites

1. **gcloud CLI installed**
   ```bash
   brew install --cask google-cloud-sdk  # macOS
   ```

2. **Authenticated with GCP**
   ```bash
   make gcp-authenticate
   ```

3. **Docker image exists in Artifact Registry**
   - Image: `asia-southeast1-docker.pkg.dev/image-478813/a1-moments/face-api:latest`

## Deployment Options

### Option 1: Cloud Run (Recommended) ⭐

Cloud Run is recommended for Docker-based deployments with automatic scaling.

#### Quick Deploy
```bash
make deploy-quick
```

This will:
1. Configure GCP project
2. Deploy to Cloud Run
3. Display the service URL

#### Full Deploy Command
```bash
make deploy-cloudrun
```

#### Get Service URL
```bash
make cloudrun-url
```

#### View Logs
```bash
# View recent logs
make cloudrun-logs

# Tail logs in real-time
make cloudrun-tail-logs
```

### Option 2: App Engine Flexible

App Engine Flexible also supports custom Docker images.

#### Deploy to App Engine
```bash
# App.yaml already exists, so just deploy
make deploy-appengine
```

#### Open App in Browser
```bash
make appengine-browse
```

#### View Logs
```bash
make appengine-logs
```

## Configuration

### Environment Variables

Update these in the Makefile or app.yaml:

```makefile
# Makefile variables
GCP_PROJECT := image-478813
GCP_REGION := asia-southeast1
DOCKER_IMAGE := asia-southeast1-docker.pkg.dev/image-478813/a1-moments/face-api:latest
CLOUD_RUN_SERVICE := face-api
```

### Update Docker Image

If you need to rebuild and push a new image:

```bash
# Build and push
make docker-build-and-push

# Or just push existing image
make docker-push
```

## Cloud Run Configuration

Current settings:
- **Memory**: 4 GB
- **CPU**: 2 vCPUs
- **Timeout**: 3600 seconds (1 hour)
- **Max instances**: 10
- **Authentication**: Public (unauthenticated)

### Deploy with Secrets (Optional)

For sensitive data like API keys:

```bash
make deploy-cloudrun-with-secrets
```

Update the command in Makefile to include your secrets.

## App Engine Configuration

Current settings (in `app.yaml`):
- **Scaling**: Manual (1 instance)
- **CPU**: 2 cores
- **Memory**: 4 GB
- **Disk**: 10 GB

### Modify app.yaml

Edit environment variables in `app.yaml`:
```yaml
env_variables:
  QDRANT_URL: 'your-qdrant-url'
  QDRANT_PORT: '6333'
  QDRANT_API_KEY: 'your-api-key'
```

## Testing Deployed Service

### Cloud Run
```bash
# Get URL
URL=$(make cloudrun-url)

# Test health
curl $URL/

# Test copy-drive-to-gcs
curl -X POST $URL/copy-drive-to-gcs \
  -H "Content-Type: application/json" \
  -d '{
    "drive_link": "https://drive.google.com/drive/folders/YOUR_FOLDER_ID",
    "gcs_bucket": "a1-moments",
    "gcs_directory": "photos/event"
  }'
```

### App Engine
```bash
# Get URL from browser or gcloud
gcloud app browse

# Or get URL directly
URL=$(gcloud app describe --format='value(defaultHostname)')
curl https://$URL/
```

## Monitoring & Logs

### Cloud Run
```bash
# View logs
make cloudrun-logs

# Tail logs
make cloudrun-tail-logs

# View in Cloud Console
open "https://console.cloud.google.com/run/detail/asia-southeast1/face-api/logs?project=image-478813"
```

### App Engine
```bash
# Tail logs
make appengine-logs

# List versions
make appengine-versions

# View in Cloud Console
open "https://console.cloud.google.com/appengine/versions?project=image-478813"
```

## Rollback & Cleanup

### Cloud Run
```bash
# Delete service
make cloudrun-delete
```

### App Engine
```bash
# Stop version
gcloud app versions stop VERSION_ID --project=image-478813

# Delete version
gcloud app versions delete VERSION_ID --project=image-478813
```

## Cost Optimization

### Cloud Run
- **Free tier**: 2 million requests/month
- **Pricing**: Pay per request + compute time
- **Auto-scaling**: Scales to zero when not in use

### App Engine Flexible
- **No free tier**
- **Always running**: At least 1 instance
- **More expensive** than Cloud Run for sporadic traffic

**Recommendation**: Use Cloud Run for better cost efficiency with automatic scaling to zero.

## Troubleshooting

### Check Service Account Permissions
```bash
# Service account should have these roles:
# - Storage Admin (for GCS)
# - Cloud Run Admin (for deployment)
# - Artifact Registry Reader (for pulling images)
```

### Update Service Account in Cloud Run
```bash
make deploy-cloudrun
# Update the --service-account flag in Makefile
```

### Check Logs for Errors
```bash
make cloudrun-tail-logs
# or
make appengine-logs
```

### Redeploy
```bash
# Cloud Run
make deploy-quick

# App Engine
make deploy-appengine
```

## Quick Reference

| Command | Description |
|---------|-------------|
| `make deploy-quick` | Quick deploy to Cloud Run |
| `make deploy-cloudrun` | Full Cloud Run deployment |
| `make deploy-appengine` | Deploy to App Engine |
| `make cloudrun-url` | Get Cloud Run URL |
| `make cloudrun-logs` | View Cloud Run logs |
| `make appengine-browse` | Open App Engine in browser |
| `make docker-build-and-push` | Build and push new image |
| `make gcp-authenticate` | Authenticate with GCP |

## Support

For issues, check:
1. Logs: `make cloudrun-logs` or `make appengine-logs`
2. Service status in Cloud Console
3. IAM permissions for service account
