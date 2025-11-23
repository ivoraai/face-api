# API Reference - All Curl Commands

## Health & Status

```bash
# Health check
curl http://localhost:8000/
```

---

## Image Processing Endpoints

### Get Faces
```bash
curl -X POST http://localhost:8000/get-faces \
  -F "image=@image.png"
```

### Get Features
```bash
curl -X POST http://localhost:8000/get-features \
  -F "image=@image.png"
```

### Get Embeddings
```bash
curl -X POST http://localhost:8000/get-embedding \
  -F "image=@image.png"
```

---

## Search Endpoint (with filters)

### Search - All
```bash
curl -X POST http://localhost:8000/search-face \
  -F "image=@image.png" \
  -d "confidence=0.8&limit=5"
```

### Search - By Collection Only
```bash
curl -X POST "http://localhost:8000/search-face?collection_name=face_embeddings&confidence=0.8&limit=5" \
  -F "image=@image.png"
```

### Search - By Group Only
```bash
curl -X POST "http://localhost:8000/search-face?group_id=engagement_photos&confidence=0.8&limit=5" \
  -F "image=@image.png"
```

### Search - By Collection + Group
```bash
curl -X POST "http://localhost:8000/search-face?collection_name=face_embeddings&group_id=engagement_photos&confidence=0.8&limit=10" \
  -F "image=@image.png"
```

---

## Digest Endpoint (Bulk Processing)

### Digest - Local Directory
```bash
curl -X POST http://localhost:8000/digest \
  -H 'Content-Type: application/json' \
  -d '{
    "local_dir_path": "/Users/harshitsmac/Documents/dr/test_digest_images",
    "group_id": "engagement_photos",
    "collection": "face_embeddings",
    "confidence": 0.7,
    "threads": 4
  }'
```

### Digest - S3 Bucket
```bash
curl -X POST http://localhost:8000/digest \
  -H 'Content-Type: application/json' \
  -d '{
    "s3_bucket": "my-bucket",
    "s3_prefix": "faces/",
    "group_id": "s3_images",
    "collection": "face_embeddings",
    "confidence": 0.7,
    "threads": 4
  }'
```

### Get All Digests
```bash
curl http://localhost:8000/get-digests
```

### Get Specific Digest
```bash
curl http://localhost:8000/get-digests/{JOB_ID}
```

**Example:**
```bash
curl http://localhost:8000/get-digests/digest-a1525296-5262-43bb-8e89-42ad3414392e
```

---

## Cluster Endpoint

### Cluster Faces
```bash
curl -X POST http://localhost:8000/cluster-faces \
  -H 'Content-Type: application/json' \
  -d '{"group_id": "engagement_photos"}'
```

---

## Common Patterns

### Complete Workflow

**Step 1: Digest images**
```bash
JOB_RESPONSE=$(curl -s -X POST http://localhost:8000/digest \
  -H 'Content-Type: application/json' \
  -d '{
    "local_dir_path": "/Users/harshitsmac/Documents/dr/test_digest_images",
    "group_id": "event1",
    "collection": "face_embeddings",
    "confidence": 0.7,
    "threads": 4
  }')

JOB_ID=$(echo $JOB_RESPONSE | jq -r '.job_id')
echo "Digest job started: $JOB_ID"
```

**Step 2: Check progress**
```bash
curl http://localhost:8000/get-digests/$JOB_ID | jq '.status, .progress, .faces_processed, .total_images'
```

**Step 3: Search in the group**
```bash
curl -X POST "http://localhost:8000/search-face?group_id=event1&confidence=0.8" \
  -F "image=@query_image.png"
```

**Step 4: Cluster**
```bash
curl -X POST http://localhost:8000/cluster-faces \
  -H 'Content-Type: application/json' \
  -d '{"group_id": "event1"}'
```

---

## Query Parameters Reference

### Search Parameters
- `collection_name` (optional, default: `face_embeddings`): Qdrant collection to search
- `group_id` (optional): Filter to specific group
- `confidence` (optional, default: `0.8`): Min similarity 0-1
- `limit` (optional, default: `5`): Max results per face

### Digest Parameters
- `local_dir_path` (optional): Local directory path (use OR with S3)
- `s3_bucket` (optional): S3 bucket name (use with s3_prefix)
- `s3_prefix` (optional): S3 folder prefix (use with s3_bucket)
- `group_id` (required): Group identifier
- `collection` (optional, default: `face_embeddings`): Target Qdrant collection
- `confidence` (optional, default: `0.5`): Detection confidence threshold
- `threads` (optional, default: `4`): Number of processing threads

---

## Response Examples

### Digest Start
```json
{
  "job_id": "digest-a1525296-5262-43bb-8e89-42ad3414392e",
  "status": "queued",
  "message": "Digest task queued for processing"
}
```

### Digest Status
```json
{
  "job_id": "digest-a1525296-5262-43bb-8e89-42ad3414392e",
  "group_id": "engagement_photos",
  "status": "completed",
  "progress": 100,
  "faces_processed": 3,
  "total_images": 3,
  "matched_faces": 0,
  "collection": "face_embeddings",
  "source": "/Users/harshitsmac/Documents/dr/test_digest_images",
  "confidence": 0.7,
  "threads": 4,
  "start_time": "2025-11-23T11:29:04.615305",
  "end_time": "2025-11-23T11:29:12.640760",
  "error_message": null,
  "upserted_ids": [
    "268ca4d8-ed3c-407e-8031-282a2c0da3aa",
    "00000faa-f057-413e-a2d6-7bd8e5f9b415",
    "a2cc5a80-a756-46e1-b923-9f88e55bd723"
  ]
}
```

### Get All Digests
```json
{
  "total_jobs": 1,
  "jobs": [...]
}
```

### Search Response
```json
{
  "faces_detected": 1,
  "search_results": [
    {
      "face_id": 0,
      "facial_area": {
        "x": 19,
        "y": 42,
        "w": 72,
        "h": 86
      },
      "detection_confidence": 1.0,
      "matches": [
        {
          "rank": 1,
          "similarity": 0.95,
          "image_path": "/path/to/image.png",
          "person_id": "person-123",
          "landmarks": {
            "nose": [x, y],
            "left_eye": [x, y],
            "right_eye": [x, y]
          }
        }
      ],
      "matches_found": 1
    }
  ]
}
```

---

## Error Handling

### Missing Required Field
```bash
curl -X POST http://localhost:8000/digest \
  -H 'Content-Type: application/json' \
  -d '{"local_dir_path": "/path"}'
# Returns: 422 Validation Error - missing group_id
```

### Invalid Job ID
```bash
curl http://localhost:8000/get-digests/invalid-job-id
# Returns: 404 Job not found
```

### Neither S3 nor Local Path
```bash
curl -X POST http://localhost:8000/digest \
  -H 'Content-Type: application/json' \
  -d '{"group_id": "event1"}'
# Returns: 422 Validation Error - must provide one of local_dir_path or s3_bucket+s3_prefix
```

---

## Pretty Output with jq

```bash
# Format JSON nicely
curl -s http://localhost:8000/get-digests | jq .

# Get specific field
curl -s http://localhost:8000/get-digests | jq '.jobs[0].status'

# Get array of job IDs
curl -s http://localhost:8000/get-digests | jq '.jobs[].job_id'

# Filter by status
curl -s http://localhost:8000/get-digests | jq '.jobs[] | select(.status == "completed")'
```

---

## Monitoring Tips

**Watch digest progress:**
```bash
watch "curl -s http://localhost:8000/get-digests | jq '.jobs[0] | {status, progress, faces_processed, total_images}'"
```

**Check all active jobs:**
```bash
curl -s http://localhost:8000/get-digests | jq '.jobs | length'
```

**Get job with max progress:**
```bash
curl -s http://localhost:8000/get-digests | jq '.jobs | max_by(.progress)'
```

---

## Quick Copy-Paste Commands

```bash
# Test all endpoints
curl http://localhost:8000/ && \
curl -X POST http://localhost:8000/get-faces -F "image=@im.png" | jq '.faces | length' && \
curl -X POST http://localhost:8000/get-features -F "image=@im.png" | jq '.faces[0].features' && \
curl -X POST http://localhost:8000/get-embedding -F "image=@im.png" | jq '.faces[0].embedding | length' && \
curl -X POST "http://localhost:8000/search-face?confidence=0.8" -F "image=@im.png" | jq '.search_results | length' && \
curl http://localhost:8000/get-digests | jq '.total_jobs' && \
echo "✓ All endpoints working"
```

