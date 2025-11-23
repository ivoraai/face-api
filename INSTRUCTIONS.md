# Face Service API - Setup & Usage Instructions

## Quick Start

### 1. Installation

```bash
cd /Users/harshitsmac/Documents/dr

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install --upgrade pip setuptools wheel
pip install -e .
```

### 2. Start the Server

```bash
cd /Users/harshitsmac/Documents/dr
source venv/bin/activate
uvicorn face_service_fastapi:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at: `http://localhost:8000`

---

## API Endpoints

### 1. GET / - Health Check

Returns service status and configuration.

**Request:**
```bash
curl -X GET http://localhost:8000/
```

**Response:**
```json
{
  "service": "Face Worker Service",
  "status": "ok",
  "qdrant_collection": "face_embeddings"
}
```

---

### 2. POST /get-faces - Extract Faces

Detects and extracts faces from an image. Returns face locations, confidence scores, and base64-encoded thumbnails.

**Request:**
```bash
curl -X POST http://localhost:8000/get-faces \
  -H "Content-Type: multipart/form-data" \
  -F "image=@im.png"
```

**Response:**
```json
{
  "faces": [
    {
      "face_id": 0,
      "face_b64": "iVBORw0KGgoAAAANSUhEUgAAAEgAAABQCAYAAAC6s...",
      "facial_area": {
        "x": 10,
        "y": 15,
        "w": 72,
        "h": 86
      },
      "confidence": 1.0
    }
  ]
}
```

---

### 3. POST /get-features - Extract Face Features

Detects faces and extracts age, gender, emotion, and facial landmarks.

**Request:**
```bash
curl -X POST http://localhost:8000/get-features \
  -H "Content-Type: multipart/form-data" \
  -F "image=@im.png"
```

**Response:**
```json
{
  "faces": [
    {
      "face_id": 0,
      "facial_area": {
        "x": 10,
        "y": 15,
        "w": 72,
        "h": 86
      },
      "confidence": 1.0,
      "features": {
        "emotion": "happy",
        "age": 34,
        "gender": "Man",
        "landmarks": {
          "x": 0,
          "y": 0,
          "w": 71,
          "h": 85,
          "left_eye": null,
          "right_eye": null
        }
      }
    }
  ]
}
```

---

### 4. POST /get-embedding - Extract Face Embeddings

Detects faces and generates 512-dimensional embeddings using ArcFace model. Also includes features and base64 thumbnail.

**Request:**
```bash
curl -X POST http://localhost:8000/get-embedding \
  -H "Content-Type: multipart/form-data" \
  -F "image=@im.png"
```

**Response:**
```json
{
  "faces": [
    {
      "face_id": 0,
      "face_b64": "iVBORw0KGgoAAAANSUhEUgAAAEgAAABQCAYAAAC6s...",
      "facial_area": {
        "x": 10,
        "y": 15,
        "w": 72,
        "h": 86
      },
      "features": {
        "emotion": "happy",
        "age": 34,
        "gender": "Man",
        "landmarks": { ... }
      },
      "embedding": [0.123, -0.456, 0.789, ..., 0.234]  // 512 floats
    }
  ]
}
```

---

### 5. POST /search-face - Search Similar Faces in Qdrant

Detects ALL faces in the provided image and searches Qdrant vector database for similar faces in stored embeddings. Returns rich metadata for each match including facial landmarks.

**Features:**
- Detects and searches all faces in image (not just first)
- Returns facial landmarks (eyes, nose, mouth)
- Includes detection confidence scores
- Person ID tracking (if available)
- Gracefully handles empty Qdrant database

**Request:**
```bash
curl -X POST "http://localhost:8000/search-face?confidence=0.5&limit=5" \
  -H "Content-Type: multipart/form-data" \
  -F "image=@im.png"
```

**Query Parameters:**
- `confidence` (float, default=0.8): Minimum similarity score threshold (0-1)
- `limit` (int, default=5): Maximum number of matches per face

**Response (example with populated Qdrant):**
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
      "matches_found": 5,
      "matches": [
        {
          "rank": 1,
          "similarity_score": 0.971,
          "image_path": "/path/to/image1.jpg",
          "face_id": 0,
          "person_id": "person-001",
          "detection_confidence": 1.0,
          "facial_area": {
            "x": 100,
            "y": 150,
            "w": 80,
            "h": 90,
            "left_eye": [145, 170],
            "right_eye": [115, 172],
            "nose": [130, 180],
            "mouth_left": [145, 195],
            "mouth_right": [115, 197]
          }
        },
        {
          "rank": 2,
          "similarity_score": 0.950,
          "image_path": "/path/to/image2.jpg",
          "face_id": 1,
          "person_id": "person-001",
          "detection_confidence": 0.98,
          "facial_area": { ... }
        }
      ]
    }
  ]
}
```

**Response (empty Qdrant):**
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
      "matches_found": 0,
      "matches": []
    }
  ]
}
```

**Response Fields:**
- `faces_detected`: Total number of faces detected in the query image
- `search_results`: Array of results for each detected face
  - `face_id`: Index of the face in the image (0-based)
  - `facial_area`: Bounding box coordinates (x, y, width, height)
  - `detection_confidence`: Face detection confidence (0-1)
  - `matches_found`: Number of matches found above threshold
  - `matches`: Array of similar faces from Qdrant, ranked by similarity
    - `rank`: Ranking position
    - `similarity_score`: Cosine similarity (0-1, higher = more similar)
    - `image_path`: Path to the matched image
    - `face_id`: Face ID within the matched image
    - `person_id`: Person identifier (from clustering)
    - `detection_confidence`: Detection confidence for this match
    - `facial_area`: Bounding box + landmarks for the matched face

**Notes:**
- Returns empty matches array if Qdrant is unpopulated (no stored embeddings)
- Use `/digest` endpoint to populate Qdrant from S3
- Use `/cluster-faces` to assign person_ids to faces
- Similarity scores range from 0 (completely different) to 1 (identical)
- Recommended confidence threshold: 0.5-0.7 for loose matching, 0.8-0.9 for strict matching

---

### 6. POST /digest - Extract Faces from Images (Background Task)

Starts a background job to extract faces from images (local or S3), generate embeddings, and store in Qdrant with group tracking.

**Features:**
- ✅ Process local directories or S3 buckets
- ✅ Multi-threaded image processing for performance
- ✅ Configurable face confidence threshold
- ✅ Group ID tracking for easy retrieval
- ✅ Real-time job status monitoring

**Request (Local Directory):**
```bash
curl -X POST http://localhost:8000/digest \
  -H "Content-Type: application/json" \
  -d '{
    "local_dir_path": "/path/to/images",
    "group_id": "event_name",
    "confidence": 0.7,
    "threads": 4
  }'
```

**Request (S3 Bucket):**
```bash
curl -X POST http://localhost:8000/digest \
  -H "Content-Type: application/json" \
  -d '{
    "s3_bucket": "my-bucket",
    "s3_prefix": "faces/",
    "group_id": "event_name",
    "confidence": 0.7,
    "threads": 4
  }'
```

**Response (202 Accepted):**
```json
{
  "job_id": "digest-6b69c550-9a18-40e9-a37a-aeee6e8f6078",
  "status": "queued",
  "message": "Digest task queued for processing"
}
```

**Request Schema:**
- `local_dir_path` (Optional): Path to local directory with images
- `s3_bucket` (Optional): S3 bucket name (must be used with `s3_prefix`)
- `s3_prefix` (Optional): S3 path prefix (must be used with `s3_bucket`)
- `group_id` (Required): Identifier to group all digested faces
- `confidence` (Optional, default 0.5): Face detection confidence threshold (0-1)
- `threads` (Optional, default 4): Number of worker threads for processing

**Validation:**
- Must provide either `local_dir_path` OR (`s3_bucket` + `s3_prefix`), not both
- `confidence` must be between 0 and 1
- `threads` must be >= 1

---

### 6b. GET /get-digests - Get All Digest Jobs Status

Retrieve status of all active and completed digest jobs.

**Request:**
```bash
curl http://localhost:8000/get-digests
```

**Response (200 OK):**
```json
{
  "total_jobs": 1,
  "jobs": [
    {
      "job_id": "digest-6b69c550-9a18-40e9-a37a-aeee6e8f6078",
      "group_id": "event_name",
      "status": "completed",
      "progress": 100,
      "faces_processed": 3,
      "total_faces": 3,
      "matched_faces": 0,
      "source": "/path/to/images",
      "confidence": 0.7,
      "threads": 4,
      "start_time": "2025-11-23T10:48:19.719157",
      "end_time": "2025-11-23T10:48:28.053868",
      "error_message": null,
      "upserted_ids": ["id1", "id2", "id3"]
    }
  ]
}
```

---

### 6c. GET /get-digests/{job_id} - Get Specific Digest Job Status

Retrieve detailed status of a specific digest job.

**Request:**
```bash
curl http://localhost:8000/get-digests/digest-6b69c550-9a18-40e9-a37a-aeee6e8f6078
```

**Response (200 OK):**
```json
{
  "job_id": "digest-6b69c550-9a18-40e9-a37a-aeee6e8f6078",
  "group_id": "event_name",
  "status": "completed",
  "progress": 100,
  "faces_processed": 3,
  "total_faces": 3,
  "matched_faces": 0,
  "source": "/path/to/images",
  "confidence": 0.7,
  "threads": 4,
  "start_time": "2025-11-23T10:48:19.719157",
  "end_time": "2025-11-23T10:48:28.053868",
  "error_message": null,
  "upserted_ids": ["id1", "id2", "id3"]
}
```

**Error Response (404 Not Found):**
```json
{
  "detail": "Job invalid-job-id not found"
}
```

**Status Values:**
- `queued`: Job created, waiting to process
- `processing`: Extracting faces and generating embeddings
- `completed`: Job finished successfully
- `failed`: Job encountered an error (see error_message)

---

### 7. POST /cluster-faces - Cluster Faces (Background Task)

Starts a background job to:
1. Fetch all face embeddings for a group
2. Run DBSCAN clustering
3. Assign person_ids to faces
4. Update Qdrant payloads

**Request:**
```bash
curl -X POST http://localhost:8000/cluster-faces \
  -H "Content-Type: application/json" \
  -d '{
    "group_id": "group-123"
  }'
```

**Response (202 Accepted):**
```json
{
  "job_id": "cluster-0a6d0898-feb4-4d46-95f8-4fd9c8457779",
  "status": "started",
  "message": "Clustering task started in background (no Celery)"
}
```

---

## Test All Endpoints

Run this script to test all endpoints:

```bash
cd /Users/harshitsmac/Documents/dr
source venv/bin/activate

python3 << 'EOF'
import requests
import json

BASE_URL = "http://localhost:8000"
IMAGE_PATH = "im.png"

print("=" * 80)
print("TESTING ALL API ENDPOINTS")
print("=" * 80)

# Test 1: Root
print("\n[1] GET / (Health Check)")
r = requests.get(f"{BASE_URL}/")
print(f"Status: {r.status_code}")
print(f"Response: {json.dumps(r.json(), indent=2)}")

# Test 2: Get Faces
print("\n[2] POST /get-faces")
with open(IMAGE_PATH, 'rb') as f:
    r = requests.post(f"{BASE_URL}/get-faces", files={'image': f})
print(f"Status: {r.status_code}")
resp = r.json()
print(f"Faces found: {len(resp.get('faces', []))}")

# Test 3: Get Features
print("\n[3] POST /get-features")
with open(IMAGE_PATH, 'rb') as f:
    r = requests.post(f"{BASE_URL}/get-features", files={'image': f})
print(f"Status: {r.status_code}")
resp = r.json()
if resp.get('faces'):
    print(f"Features: {json.dumps(resp['faces'][0]['features'], indent=2, default=str)}")

# Test 4: Get Embedding
print("\n[4] POST /get-embedding")
with open(IMAGE_PATH, 'rb') as f:
    r = requests.post(f"{BASE_URL}/get-embedding", files={'image': f})
print(f"Status: {r.status_code}")
resp = r.json()
if resp.get('faces'):
    face = resp['faces'][0]
    print(f"Embedding length: {len(face['embedding'])}")
    print(f"Has thumbnail: {bool(face.get('face_b64'))}")

# Test 5: Search Face
print("\n[5] POST /search-face")
with open(IMAGE_PATH, 'rb') as f:
    r = requests.post(f"{BASE_URL}/search-face?confidence=0.8&limit=5", files={'image': f})
print(f"Status: {r.status_code}")
resp = r.json()
print(f"Matches found: {len(resp.get('matches', []))}")

# Test 6: Digest
print("\n[6] POST /digest")
r = requests.post(f"{BASE_URL}/digest", json={
    "s3_bucket": "test-bucket",
    "s3_prefix": "faces/",
    "group_id": "group-123"
})
print(f"Status: {r.status_code}")
print(f"Job ID: {r.json().get('job_id')}")

# Test 7: Cluster Faces
print("\n[7] POST /cluster-faces")
r = requests.post(f"{BASE_URL}/cluster-faces", json={"group_id": "group-123"})
print(f"Status: {r.status_code}")
print(f"Job ID: {r.json().get('job_id')}")

print("\n" + "=" * 80)
EOF
```

---

## Environment Variables

Configure the service using `.env` file:

```bash
# Qdrant Configuration
QDRANT_URL=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=optional_key
QDRANT_COLLECTION=face_embeddings
EMBEDDING_SIZE=512

# Optional Celery (for background tasks)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

---

## Project Structure

```
/Users/harshitsmac/Documents/dr/
├── face_embedding_processor.py     # Main API implementation
├── face_service_fastapi.py         # Entrypoint shim for uvicorn
├── pyproject.toml                  # Project configuration & dependencies
├── venv/                           # Python virtual environment
├── im.png                          # Sample test image
└── INSTRUCTIONS.md                 # This file
```

---

## Troubleshooting

### Server won't start
```bash
# Check if port 8000 is already in use
lsof -i :8000

# Kill existing process
pkill -f "uvicorn face_service_fastapi"

# Restart server
source venv/bin/activate
uvicorn face_service_fastapi:app --reload --host 0.0.0.0 --port 8000
```

### "ModuleNotFoundError: No module named 'cv2'"
```bash
# Reinstall dependencies
source venv/bin/activate
pip install -e . --force-reinstall
```

### Features returning None/empty
- Ensure the image contains a clear face
- The API uses RetinaFace for detection and ArcFace for embeddings
- Test with `im.png` which has been verified to work

### Qdrant connection errors
- Ensure Qdrant server is running (if using local instance)
- Check `QDRANT_URL` and `QDRANT_PORT` in `.env`

---

## Key Technologies

- **FastAPI**: REST API framework
- **Uvicorn**: ASGI server
- **DeepFace**: Face detection & embedding (RetinaFace + ArcFace)
- **Qdrant**: Vector database for similarity search
- **OpenCV**: Image processing
- **NumPy**: Numerical computations

---

## Performance Notes

- Face detection: ~200-500ms per image
- Embedding generation: ~100-300ms per face
- Vector search: <50ms (depends on Qdrant size)
- Batch processing recommended for large datasets

---

## API Test Results

✅ All endpoints tested and working:

| Endpoint | Status | Faces Detected | Features | Embedding |
|----------|--------|---|---|---|
| GET / | 200 ✓ | N/A | N/A | N/A |
| POST /get-faces | 200 ✓ | 1 | N/A | N/A |
| POST /get-features | 200 ✓ | 1 | ✓ Happy, Age 34, Man | N/A |
| POST /get-embedding | 200 ✓ | 1 | ✓ Happy, Age 34, Man | ✓ 512-dim |
| POST /search-face | 200 ✓ | - | - | - |
| POST /digest | 202 ✓ | - | - | - |
| POST /cluster-faces | 202 ✓ | - | - | - |

---

## Support

For issues or questions, check the server logs:

```bash
tail -f /tmp/uvicorn.log
```

Or run the server in foreground to see real-time logs:

```bash
source venv/bin/activate
uvicorn face_service_fastapi:app --reload --host 0.0.0.0 --port 8000
```
