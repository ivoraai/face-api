# Digest Endpoint Testing Guide

## Overview
The `/digest` endpoint now supports multi-threaded image processing from local directories or S3 buckets with job tracking and status monitoring.

## New Features
- ✅ **Local Directory Support**: Process images from local filesystem with `local_dir_path`
- ✅ **S3 Support**: Process images from S3 with `s3_bucket` + `s3_prefix` (stub - ready for boto3)
- ✅ **Confidence Threshold**: Control minimum face detection confidence with `confidence` parameter (0-1)
- ✅ **Multi-Threading**: Process multiple images in parallel with `threads` parameter
- ✅ **Group ID Tracking**: Associate all digested faces with a `group_id` for easy retrieval
- ✅ **Job Tracking**: Monitor digest progress with new `/get-digests` endpoints
- ✅ **Real-time Status**: Get progress updates including faces processed, total faces, and thread count

## Endpoints

### 1. POST /digest - Start Digest Job
Initiates a background job to extract faces from images.

**Request Schema:**
```json
{
  "local_dir_path": "/path/to/images",    // Optional: local directory path
  "s3_bucket": "bucket-name",             // Optional: S3 bucket (with s3_prefix)
  "s3_prefix": "path/prefix",             // Optional: S3 prefix (with s3_bucket)
  "group_id": "event_name",               // Required: group identifier for faces
  "confidence": 0.7,                      // Optional (default 0.5): face confidence threshold
  "threads": 4                            // Optional (default 4): number of worker threads
}
```

**Validation Rules:**
- Must provide either `local_dir_path` OR (`s3_bucket` + `s3_prefix`)
- Cannot provide both local and S3 paths simultaneously
- `confidence` must be between 0 and 1
- `threads` must be >= 1

**Response (202 Accepted):**
```json
{
  "job_id": "digest-6b69c550-9a18-40e9-a37a-aeee6e8f6078",
  "status": "queued",
  "message": "Digest task queued for processing"
}
```

### 2. GET /get-digests - Get All Digest Jobs
Retrieve status of all active and recently completed digest jobs.

**Response:**
```json
{
  "total_jobs": 3,
  "jobs": [
    {
      "job_id": "digest-6b69c550-9a18-40e9-a37a-aeee6e8f6078",
      "group_id": "test_engagement",
      "status": "completed",
      "progress": 100,
      "faces_processed": 3,
      "total_faces": 3,
      "matched_faces": 0,
      "source": "/Users/harshitsmac/Documents/dr/test_digest_images",
      "confidence": 0.7,
      "threads": 2,
      "start_time": "2025-11-23T10:48:19.719157",
      "end_time": "2025-11-23T10:48:28.053868",
      "error_message": null,
      "upserted_ids": ["e49e6f3a-38ec-4b9b-8ae8-e20a34d0e3e6", "9a0a4b00-c5de-416d-8b69-0effb792d46d", "30cb61bd-4a61-42d6-8338-cfac417476f6"]
    }
  ]
}
```

**Status Values:**
- `queued`: Job created, waiting to start
- `processing`: Currently extracting faces and generating embeddings
- `completed`: Job finished successfully
- `failed`: Job encountered an error

### 3. GET /get-digests/{job_id} - Get Specific Job Status
Retrieve detailed status of a specific digest job.

**Response (200 OK or 404 Not Found):**
```json
{
  "job_id": "digest-6b69c550-9a18-40e9-a37a-aeee6e8f6078",
  "group_id": "test_engagement",
  "status": "completed",
  "progress": 100,
  "faces_processed": 3,
  "total_faces": 3,
  "matched_faces": 0,
  "source": "/Users/harshitsmac/Documents/dr/test_digest_images",
  "confidence": 0.7,
  "threads": 2,
  "start_time": "2025-11-23T10:48:19.719157",
  "end_time": "2025-11-23T10:48:28.053868",
  "error_message": null,
  "upserted_ids": [...]
}
```

## Test Cases

### Test 1: Local Directory Digest
**Request:**
```bash
curl -X POST http://localhost:8000/digest \
  -H "Content-Type: application/json" \
  -d '{
    "local_dir_path": "/Users/harshitsmac/Documents/dr/test_digest_images",
    "group_id": "test_engagement",
    "confidence": 0.7,
    "threads": 2
  }'
```

**Expected:**
- ✅ Returns 202 with job_id
- ✅ Job status shows "processing" or "completed"
- ✅ Faces are extracted and upserted to Qdrant
- ✅ Group ID is stored in Qdrant payload

### Test 2: Check Digest Status
**Request:**
```bash
curl http://localhost:8000/get-digests/digest-6b69c550-9a18-40e9-a37a-aeee6e8f6078
```

**Expected:**
- ✅ Returns 200 with detailed job information
- ✅ Progress field updates from 0 to 100
- ✅ faces_processed increases as images are processed
- ✅ Timestamps show accurate start/end times

### Test 3: Concurrent Digest Jobs
**Request:**
```bash
# Job 1
curl -X POST http://localhost:8000/digest \
  -d '{"local_dir_path": "/path1", "group_id": "group1", "threads": 2}'

# Job 2  
curl -X POST http://localhost:8000/digest \
  -d '{"local_dir_path": "/path2", "group_id": "group2", "threads": 3}'

# Check all
curl http://localhost:8000/get-digests | jq '.jobs[] | {job_id, status, progress}'
```

**Expected:**
- ✅ Both jobs show in /get-digests
- ✅ Jobs process independently
- ✅ Each maintains separate thread pool
- ✅ Status updates correctly for each job

### Test 4: Error Handling
**Request (Invalid Job ID):**
```bash
curl http://localhost:8000/get-digests/invalid-job-id
```

**Expected:**
- ✅ Returns 404
- ✅ Error message: "Job invalid-job-id not found"

**Request (Missing Required Path):**
```bash
curl -X POST http://localhost:8000/digest \
  -H "Content-Type: application/json" \
  -d '{
    "group_id": "test",
    "confidence": 0.7
  }'
```

**Expected:**
- ✅ Returns 422
- ✅ Error message: "Either s3_bucket+s3_prefix or local_dir_path must be provided"

**Request (Both Paths Provided):**
```bash
curl -X POST http://localhost:8000/digest \
  -H "Content-Type: application/json" \
  -d '{
    "local_dir_path": "/path",
    "s3_bucket": "bucket",
    "s3_prefix": "prefix",
    "group_id": "test"
  }'
```

**Expected:**
- ✅ Returns 422
- ✅ Error message: "Cannot specify both S3 and local directory paths"

### Test 5: Verify Digested Faces are Searchable
**Request:**
```bash
# Start digest
JOB=$(curl -s -X POST http://localhost:8000/digest \
  -d '{
    "local_dir_path": "/path",
    "group_id": "search_test"
  }' | jq -r '.job_id')

# Wait for completion
sleep 5

# Search for a face from digested images
curl -X POST http://localhost:8000/search-face \
  -F "image=@test_image.png" \
  -F "group_id=search_test" \
  -F "confidence=0.5"
```

**Expected:**
- ✅ Search returns matches from digested faces
- ✅ Matches include correct group_id in payload
- ✅ Similarity scores and landmarks are included

### Test 6: Multi-Threading Efficiency
**Request:**
```bash
# Create directory with 10 images
mkdir -p /tmp/large_digest_test
for i in {1..10}; do
  cp test_image.png /tmp/large_digest_test/image_$i.png
done

# Process with different thread counts
time curl -X POST http://localhost:8000/digest \
  -d '{
    "local_dir_path": "/tmp/large_digest_test",
    "group_id": "thread_test_1",
    "threads": 1
  }'

time curl -X POST http://localhost:8000/digest \
  -d '{
    "local_dir_path": "/tmp/large_digest_test",
    "group_id": "thread_test_4",
    "threads": 4
  }'
```

**Expected:**
- ✅ Higher thread count completes faster
- ✅ Progress updates correctly track all faces
- ✅ Both jobs complete successfully

## Job Response Fields Explained

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | string | Unique identifier for the digest job |
| `group_id` | string | Group identifier associated with all digested faces |
| `status` | string | Current status: queued/processing/completed/failed |
| `progress` | integer | Completion percentage (0-100) |
| `faces_processed` | integer | Number of faces extracted and upserted |
| `total_faces` | integer | Total faces found across all images |
| `matched_faces` | integer | Reserved for future match tracking |
| `source` | string | Source path (local or S3 URI) |
| `confidence` | float | Face detection confidence threshold used |
| `threads` | integer | Number of worker threads used |
| `start_time` | ISO 8601 | When the job started |
| `end_time` | ISO 8601 | When the job completed (null if still processing) |
| `error_message` | string | Error details if job failed (null if successful) |
| `upserted_ids` | array | List of face IDs successfully upserted to Qdrant |

## Implementation Details

### Threading Model
- Uses Python `concurrent.futures.ThreadPoolExecutor`
- Each image is processed independently in thread pool
- Progress updates in real-time
- Thread count is configurable (default 4)

### Face Processing Pipeline
1. **Image Collection**: Gather all supported image files (jpg, png, jpeg)
2. **Face Extraction**: Use RetinaFace to detect faces in each image
3. **Embedding Generation**: Use ArcFace to generate 512-dim embeddings
4. **Qdrant Upsert**: Store embeddings with metadata (group_id, image_path, facial_area, timestamp)
5. **Progress Tracking**: Update job status after each batch

### Metadata Stored in Qdrant
```python
{
  'group_id': 'event_name',
  'image_path': '/path/to/image.jpg',
  'face_index': 0,
  'detection_confidence': 0.95,
  'facial_area': {
    'x': 100, 'y': 150, 'w': 50, 'h': 60
  },
  'timestamp': '2025-11-23T10:48:19.719157'
}
```

## Performance Benchmarks

| Scenario | Configuration | Result |
|----------|---------------|--------|
| Single Image | 4 threads | ~2 seconds |
| 3 Images | 2 threads | ~9 seconds |
| 3 Images | 4 threads | ~9 seconds |
| 10 Images | 1 thread | ~20 seconds (est.) |
| 10 Images | 4 threads | ~7 seconds (est.) |

## Integration with Other Endpoints

### After Digest: Search Digested Faces
```bash
# 1. Start digest
curl -X POST /digest -d '{"local_dir_path": "/path", "group_id": "engagement"}'

# 2. Wait for completion
curl /get-digests

# 3. Search with digested faces
curl -X POST /search-face \
  -F "image=@query.jpg" \
  -F "group_id=engagement"
```

### After Digest: Cluster Faces
```bash
# 1. Digest images
curl -X POST /digest -d '{"local_dir_path": "/path", "group_id": "event"}'

# 2. Cluster faces in group
curl -X POST /cluster-faces -d '{"group_id": "event"}'
```

## Future Enhancements

1. **S3 Support**: Implement boto3 integration for S3 listing
2. **Persistent Job History**: Store job metadata in database
3. **Filtering**: Get digests filtered by group_id, date range, status
4. **Resume**: Resume interrupted digest jobs
5. **Batch Operations**: Delete/re-process specific digest jobs
6. **Webhooks**: Notify external systems on job completion
7. **Progress Streaming**: WebSocket stream of real-time progress updates

## Troubleshooting

**Issue: Job shows "processing" for a long time**
- Solution: Check /tmp/server.log for errors
- Check that image files exist and are valid
- Increase threads for faster processing

**Issue: No faces detected**
- Solution: Verify image quality (must have clear faces)
- Lower confidence threshold (e.g., 0.3 instead of 0.7)
- Check image format support (jpg, png, jpeg)

**Issue: Faces not appearing in search**
- Solution: Verify digest job completed successfully
- Use correct group_id in search request
- Check /get-digests to confirm faces were processed

**Issue: Out of memory with many images**
- Solution: Reduce threads parameter
- Process images in batches with separate digest jobs
- Increase available system memory
