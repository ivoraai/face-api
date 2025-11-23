# Digest Corrections & Updates - Summary

## Changes Made

### 1. **Digest Endpoint - Added `collection` Field**

**Before:**
```json
{
  "s3_bucket": "my-bucket",
  "s3_prefix": "faces/",
  "group_id": "group-123"
}
```

**After:**
```json
{
  "local_dir_path": "/path/to/images",
  "group_id": "event_name",
  "collection": "face_embeddings",
  "confidence": 0.7,
  "threads": 4
}
```

**Purpose:** The `collection` field specifies which Qdrant collection to upsert faces into, providing flexibility to use multiple collections.

---

### 2. **Digest Response - Changed `total_faces` to `total_images`**

**Before:**
```json
{
  "job_id": "digest-abc123...",
  "group_id": "engagement_photos",
  "status": "processing",
  "total_faces": 16,
  "faces_processed": 12
}
```

**After:**
```json
{
  "job_id": "digest-abc123...",
  "group_id": "engagement_photos",
  "status": "processing",
  "total_images": 16,
  "faces_processed": 12,
  "collection": "face_embeddings"
}
```

**Rationale:**
- `total_images`: Number of image files being processed
- `faces_processed`: Number of faces actually extracted and upserted to Qdrant
- These are different metrics - one image can contain multiple faces

---

### 3. **Search-Face Endpoint - Added Filters**

**Enhanced Query Parameters:**
```bash
# Before: only confidence and limit
curl -X POST "http://localhost:8000/search-face?confidence=0.8&limit=5" \
  -F "image=@image.png"

# After: added collection_name and group_id filters
curl -X POST "http://localhost:8000/search-face?collection_name=face_embeddings&group_id=engagement_photos&confidence=0.8&limit=5" \
  -F "image=@image.png"
```

**New Query Parameters:**
- `collection_name` (optional): Specify which Qdrant collection to search (default: `face_embeddings`)
- `group_id` (optional): Filter results to only faces from a specific group
- `confidence` (optional): Minimum similarity threshold 0-1 (default: 0.8)
- `limit` (optional): Max matches per face to return (default: 5)

---

## API Usage Examples

### Digest with Local Directory
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

**Response:**
```json
{
  "job_id": "digest-a1525296-5262-43bb-8e89-42ad3414392e",
  "status": "queued",
  "message": "Digest task queued for processing"
}
```

### Get All Digests
```bash
curl http://localhost:8000/get-digests
```

**Response:**
```json
{
  "total_jobs": 1,
  "jobs": [
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
  ]
}
```

### Search with Group Filter
```bash
curl -X POST "http://localhost:8000/search-face?group_id=engagement_photos&confidence=0.8&limit=5" \
  -F "image=@image.png"
```

### Search with Collection + Group Filter
```bash
curl -X POST "http://localhost:8000/search-face?collection_name=face_embeddings&group_id=engagement_photos&confidence=0.8&limit=10" \
  -F "image=@image.png"
```

---

## Digest Status Fields Explained

| Field | Meaning |
|-------|---------|
| `job_id` | Unique identifier for this digest job |
| `group_id` | Group identifier for organizing faces |
| `status` | Current state: `queued` → `processing` → `completed` (or `failed`) |
| `progress` | Percentage complete (0-100) |
| `faces_processed` | Number of faces extracted and upserted |
| `total_images` | Total number of image files processed |
| `collection` | Qdrant collection name where faces were stored |
| `source` | Source path (local dir or S3) |
| `confidence` | Detection confidence threshold used |
| `threads` | Number of threads used for parallel processing |
| `start_time` | When the job started (ISO format) |
| `end_time` | When the job completed (null if still processing) |
| `error_message` | Error details if status is `failed` |
| `upserted_ids` | List of face IDs added to Qdrant |

---

## Key Improvements

✅ **Flexible Collections**: Choose which Qdrant collection to use via `collection` parameter  
✅ **Clear Metrics**: `total_images` vs `faces_processed` distinction  
✅ **Targeted Search**: Filter by collection and/or group_id to narrow results  
✅ **Multi-threading**: Configurable thread count for faster processing  
✅ **Job Tracking**: Monitor active digestion processes in real-time  
✅ **Local + S3**: Support for both local directories and S3 paths  

---

## File Modifications

**Modified:** `/Users/harshitsmac/Documents/dr/face_embedding_processor.py`

Changes:
- Line ~570: Updated `DigestRequest` model with `collection` field
- Line ~430: Changed `total_faces` → `total_images` in job tracking
- Line ~440: Added `collection` to ACTIVE_DIGESTS tracking
- Line ~507: Pass `collection` parameter to `qclient.upsert()`
- Line ~628: Updated `digest_worker()` function signature with `collection` parameter
- Line ~304: Enhanced `/search-face` endpoint with `collection_name` and `group_id` parameters
- Line ~365-375: Added Qdrant filter logic for group_id filtering

**Updated:** `/Users/harshitsmac/Documents/dr/API_TEST_COMMANDS.sh`

Added comprehensive curl examples for all endpoints with new parameters.

---

## Testing

### Test 1: Digest with Local Directory
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
✅ Returns: `202 Accepted` with `job_id`

### Test 2: Get All Digests
```bash
curl http://localhost:8000/get-digests
```
✅ Returns: List of active/recent digest jobs with status

### Test 3: Search with Group Filter
```bash
curl -X POST "http://localhost:8000/search-face?group_id=engagement_photos&confidence=0.8" \
  -F "image=@image.png"
```
✅ Returns: Search results filtered to the specified group

---

## Complete Workflow

1. **Digest images** from local directory with threading:
   ```bash
   curl -X POST http://localhost:8000/digest \
     -H 'Content-Type: application/json' \
     -d '{
       "local_dir_path": "/path/to/images",
       "group_id": "event1",
       "collection": "face_embeddings",
       "confidence": 0.7,
       "threads": 4
     }'
   ```

2. **Check progress** of digest job:
   ```bash
   curl http://localhost:8000/get-digests
   ```

3. **Search** for similar faces within that group:
   ```bash
   curl -X POST "http://localhost:8000/search-face?group_id=event1&confidence=0.8" \
     -F "image=@query.png"
   ```

4. **Cluster** faces in the group:
   ```bash
   curl -X POST http://localhost:8000/cluster-faces \
     -H 'Content-Type: application/json' \
     -d '{"group_id": "event1"}'
   ```

---

## Notes

- **Either/Or for Digest**: Use either `local_dir_path` OR (`s3_bucket` + `s3_prefix`), not both
- **Collection Flexibility**: Different digest jobs can write to different Qdrant collections
- **Search Filters**: Qdrant may require indexes for efficient group_id filtering
- **Threading**: More threads = faster processing but higher resource usage
- **Progress**: Monitor via `/get-digests` endpoint for real-time status

