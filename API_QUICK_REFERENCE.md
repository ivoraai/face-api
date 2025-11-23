# Face Service API - Quick Reference Card

## Server Setup

```bash
# Start server
cd /Users/harshitsmac/Documents/dr
source venv/bin/activate
uvicorn face_service_fastapi:app --reload --host 0.0.0.0 --port 8000

# Test
curl http://localhost:8000/
```

---

## API Endpoints (7 Total)

### 1️⃣ GET / - Health Check
```bash
curl http://localhost:8000/
```
Returns: `{service, status, qdrant_collection}`

---

### 2️⃣ POST /get-faces - Extract Faces from Image
```bash
curl -X POST http://localhost:8000/get-faces \
  -F "image=@image.jpg"
```
Returns: `{faces_detected: N, faces: [{facial_area, detection_confidence, face_b64}]}`

---

### 3️⃣ POST /get-features - Get Face Attributes
```bash
curl -X POST http://localhost:8000/get-features \
  -F "image=@image.jpg"
```
Returns: `{faces: [{age, gender, expression, ethnicity, emotion}]}`

---

### 4️⃣ POST /get-embedding - Get Face Embeddings
```bash
curl -X POST http://localhost:8000/get-embedding \
  -F "image=@image.jpg"
```
Returns: `{faces: [{embedding: [512-dim vector], face_b64}]}`

---

### 5️⃣ POST /search-face - Search Similar Faces
```bash
curl -X POST http://localhost:8000/search-face \
  -F "image=@query.jpg" \
  -F "group_id=engagement" \
  -F "confidence=0.5" \
  -F "limit=5"
```
Returns:
```json
{
  "faces_detected": 1,
  "search_results": [{
    "face_id": 0,
    "detection_confidence": 1.0,
    "matches_found": 5,
    "matches": [{
      "rank": 1,
      "similarity_score": 0.97,
      "image_path": "/path/image.jpg",
      "facial_area": {x, y, w, h},
      "detection_confidence": 1.0
    }]
  }]
}
```

---

### 6️⃣ POST /digest - Extract Faces from Directory
```bash
# Local directory
curl -X POST http://localhost:8000/digest \
  -H "Content-Type: application/json" \
  -d '{
    "local_dir_path": "/path/to/images",
    "group_id": "event_name",
    "confidence": 0.7,
    "threads": 4
  }'

# S3 bucket
curl -X POST http://localhost:8000/digest \
  -H "Content-Type: application/json" \
  -d '{
    "s3_bucket": "my-bucket",
    "s3_prefix": "path/",
    "group_id": "event_name",
    "confidence": 0.7,
    "threads": 4
  }'
```
Returns: `{job_id, status: "queued", message}`

**Parameters:**
- Either `local_dir_path` OR (`s3_bucket` + `s3_prefix`)
- `group_id` (required): Group identifier for faces
- `confidence` (optional, default 0.5): Face confidence 0-1
- `threads` (optional, default 4): Worker threads

---

### 6b️⃣ GET /get-digests - Get All Digest Jobs
```bash
curl http://localhost:8000/get-digests
```
Returns:
```json
{
  "total_jobs": 3,
  "jobs": [{
    "job_id": "digest-xxx",
    "group_id": "event_name",
    "status": "completed",
    "progress": 100,
    "faces_processed": 5,
    "total_faces": 5,
    "source": "/path/to/images",
    "start_time": "2025-11-23T...",
    "end_time": "2025-11-23T...",
    "upserted_ids": ["id1", "id2", ...]
  }]
}
```

**Status Values:**
- `queued` - Waiting to start
- `processing` - Currently running
- `completed` - Finished successfully
- `failed` - Error occurred

---

### 6c️⃣ GET /get-digests/{job_id} - Get Specific Job
```bash
curl http://localhost:8000/get-digests/digest-6b69c550-9a18-40e9-a37a-aeee6e8f6078
```
Returns: Single job object (same as /get-digests items)

Error: `{detail: "Job ... not found"}` (404)

---

### 7️⃣ POST /cluster-faces - Cluster Faces
```bash
curl -X POST http://localhost:8000/cluster-faces \
  -H "Content-Type: application/json" \
  -d '{"group_id": "event_name"}'
```
Returns: `{job_id, status: "started", message}`

---

## Quick Test Sequence

```bash
# 1. Create test directory
mkdir -p /tmp/test_faces
cp image1.jpg image2.jpg image3.jpg /tmp/test_faces/

# 2. Start digest
JOB=$(curl -s -X POST http://localhost:8000/digest \
  -H "Content-Type: application/json" \
  -d '{
    "local_dir_path": "/tmp/test_faces",
    "group_id": "test_group",
    "threads": 2
  }' | jq -r '.job_id')

echo "Digest job: $JOB"

# 3. Check status
curl http://localhost:8000/get-digests/$JOB | jq '{status, progress, faces_processed}'

# 4. Wait for completion
sleep 5

# 5. Verify all jobs
curl http://localhost:8000/get-digests | jq '.jobs[] | {group_id, status, progress}'

# 6. Search with digested faces
curl -X POST http://localhost:8000/search-face \
  -F "image=@query_image.jpg" \
  -F "group_id=test_group" \
  | jq '.search_results[0].matches_found'
```

---

## Common Workflows

### Workflow 1: Ingest Photos
```bash
# Digest photos from event
curl -X POST /digest -d '{
  "local_dir_path": "/Volumes/Photos/Event2025",
  "group_id": "engagement_2025",
  "threads": 4
}'

# Monitor
curl /get-digests | jq '.jobs[-1] | {status, progress, faces_processed}'
```

### Workflow 2: Find Similar Faces
```bash
# 1. Digest reference photos
curl -X POST /digest -d '{
  "local_dir_path": "/path/reference",
  "group_id": "reference_set"
}'

# 2. Search for matches
curl -X POST /search-face \
  -F "image=@unknown_face.jpg" \
  -F "group_id=reference_set" \
  | jq '.search_results[].matches[] | {similarity_score, image_path}'
```

### Workflow 3: Cluster Event Photos
```bash
# 1. Digest event photos
curl -X POST /digest -d '{
  "local_dir_path": "/Volumes/Event",
  "group_id": "event_photos"
}'

# 2. Wait for completion
while true; do
  STATUS=$(curl -s /get-digests | jq '.jobs[-1].status')
  [ "$STATUS" = "\"completed\"" ] && break
  sleep 1
done

# 3. Cluster faces
curl -X POST /cluster-faces -d '{"group_id": "event_photos"}'
```

---

## Response Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | OK | /search-face successful |
| 202 | Accepted (async) | /digest, /cluster-faces |
| 404 | Not Found | /get-digests/{invalid_id} |
| 422 | Validation Error | Missing required field |
| 500 | Server Error | Qdrant connection failed |

---

## Performance Tips

- **More threads = Faster processing** (up to CPU cores)
- **Lower confidence = More faces detected** (but lower precision)
- **Use group_id** to organize and search face sets efficiently
- **Check progress** with /get-digests for long-running jobs
- **Batch large directories** into multiple digest jobs to avoid memory issues

---

## Troubleshooting

**Server not responding?**
```bash
curl -v http://localhost:8000/
ps aux | grep uvicorn
```

**Digest job stuck?**
```bash
curl /get-digests | jq '.jobs[] | {job_id, status, progress, error_message}'
```

**No faces found?**
- Check image quality
- Lower confidence threshold
- Verify image format (jpg, png, jpeg)
- Check file permissions for local directories

**Search returns no matches?**
- Verify digest job completed
- Use correct group_id
- Check face quality in search image

---

## Full Documentation

- **Setup & Installation**: See `INSTRUCTIONS.md`
- **Digest Testing**: See `DIGEST_ENDPOINT_TESTS.md`
- **Implementation Details**: See `DIGEST_ENHANCEMENT_SUMMARY.md`
- **Complete API Reference**: See full `INSTRUCTIONS.md`
