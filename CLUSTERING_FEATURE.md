# Clustering Feature - `/cluster-faces` Endpoint

## Overview
The `/cluster-faces` endpoint groups similar faces together based on a **confidence threshold** and assigns them the same **person_id** in Qdrant. This enables you to:

- Identify duplicate faces of the same person across multiple images
- Group similar faces into person clusters
- Assign unique person identifiers for face recognition/retrieval

---

## Endpoint Details

### Request
```bash
POST /cluster-faces
Content-Type: application/json

{
  "group_id": "string",           # Required: group to cluster
  "collection": "string",         # Optional: Qdrant collection (default: "face_embeddings")
  "confidence": float             # Optional: similarity threshold 0-1 (default: 0.8)
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `group_id` | string | - | **Required.** The group_id to cluster faces from |
| `collection` | string | `face_embeddings` | Qdrant collection name to read/update from |
| `confidence` | float | 0.8 | Similarity threshold (0-1). Higher = stricter grouping |

### Response
```json
{
  "job_id": "cluster-uuid",
  "status": "started",
  "message": "Clustering task started in background (no Celery)"
}
```

---

## How It Works

### 1. **Fetch Faces**
- Retrieves all faces with the specified `group_id` from Qdrant
- Extracts 512-dimensional embeddings (ArcFace vectors)

### 2. **Calculate Similarity**
- Computes **cosine distances** between all face pairs
- Distance = 1 - cosine_similarity
- Two faces are grouped if: `distance ≤ (1 - confidence)`

### 3. **DBSCAN Clustering**
- Runs DBSCAN algorithm with:
  - `eps` = 1 - confidence (distance threshold)
  - `min_samples` = 1 (allow single-face clusters)
  - `metric` = "precomputed" (using cosine distances)

### 4. **Assign person_id**
- Each cluster gets a unique **person_id**: `person_{group_id}_{cluster_number}`
- All faces in cluster get this person_id via `set_payload`
- Updates Qdrant with new person_id metadata

### 5. **Return Results**
- Returns summary of clustering results
- Shows how many clusters were created
- Lists sample updated faces (first 50)

---

## Confidence Threshold Explained

The `confidence` parameter controls how strict the grouping is:

| Confidence | Distance Threshold | Behavior |
|------------|-------------------|----------|
| **0.95** | 0.05 | Very strict - only extremely similar faces group |
| **0.90** | 0.10 | Strict - high precision, may miss some duplicates |
| **0.85** | 0.15 | Balanced - good accuracy for most cases |
| **0.80** | 0.20 | Loose - may include slightly different faces |
| **0.70** | 0.30 | Very loose - groups diverse face variations |
| **0.50** | 0.50 | Extremely loose - almost everything groups |

**Recommendation**: Start with **0.85** and adjust based on results.

---

## Example Usage

### Cluster faces with 0.8 confidence
```bash
curl -X POST http://localhost:8000/cluster-faces \
  -H 'Content-Type: application/json' \
  -d '{
    "group_id": "engagement_photos",
    "collection": "face_embeddings",
    "confidence": 0.8
  }'
```

### Response
```json
{
  "job_id": "cluster-c2183ba5-099a-4acc-a4fe-4e169837c90c",
  "status": "started",
  "message": "Clustering task started in background (no Celery)"
}
```

### After clustering completes (internal result)
```json
{
  "job_id": "cluster-c2183ba5-099a-4acc-a4fe-4e169837c90c",
  "status": "completed",
  "message": "Successfully clustered 217 faces into 45 clusters",
  "group_id": "engagement_photos",
  "collection": "face_embeddings",
  "confidence": 0.8,
  "total_faces": 217,
  "clusters_created": 45,
  "faces_updated": 217,
  "updated_faces": [
    {
      "point_id": 12345,
      "original_face_id": "face_001",
      "person_id": "person_engagement_photos_1",
      "cluster_id": 0,
      "cluster_size": 5
    },
    {
      "point_id": 12346,
      "original_face_id": "face_002",
      "person_id": "person_engagement_photos_1",
      "cluster_id": 0,
      "cluster_size": 5
    },
    ...
  ]
}
```

---

## Workflow: Digest → Search → Cluster → Retrieve

```
1. POST /digest
   └─ Extract 1142 faces from 437 images
   └─ Store in Qdrant with group_id="engagement_photos"

2. POST /cluster-faces
   └─ Group 1142 faces into clusters (e.g., 45 clusters)
   └─ Assign person_id to each face
   └─ Update Qdrant payloads

3. POST /search-face + filter
   └─ Find similar faces by group_id
   └─ Retrieved faces now have person_id

4. GET /search + person_id filter
   └─ Retrieve all faces of specific person
   └─ "Show me all photos of person_engagement_photos_1"
```

---

## Key Features

✅ **Confidence-based matching** - Configure similarity threshold  
✅ **Automatic person_id assignment** - Get unique IDs for each person  
✅ **DBSCAN clustering** - Efficient grouping algorithm  
✅ **Qdrant integration** - Updates payloads directly  
✅ **Group filtering** - Cluster only specific group_id  
✅ **Custom collections** - Work with any Qdrant collection  
✅ **Background processing** - Non-blocking operation  

---

## Testing

### Test with real data
```bash
# 1. Digest 437 images
curl -X POST http://localhost:8000/digest \
  -H 'Content-Type: application/json' \
  -d '{
    "local_dir_path": "/Users/harshitsmac/Documents/dr/Jiya Maam Engagement/Candid Photo",
    "group_id": "test_cluster",
    "collection": "face_embeddings",
    "confidence": 0.7,
    "threads": 4
  }'

# 2. Wait for digest to complete, then cluster
curl -X POST http://localhost:8000/cluster-faces \
  -H 'Content-Type: application/json' \
  -d '{
    "group_id": "test_cluster",
    "collection": "face_embeddings",
    "confidence": 0.85
  }'

# 3. Search for similar faces (now with person_id)
curl -X POST http://localhost:8000/search-face \
  -F "image=@test_image.jpg"
```

---

## Parameters Summary

### ClusterRequest Model
```python
class ClusterRequest(BaseModel):
    group_id: str                           # Required
    collection: str = "face_embeddings"     # Optional
    confidence: float = 0.8                 # Optional
```

---

## Implementation Details

### Clustering Algorithm: DBSCAN

```python
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances

# Algorithm flow
1. Fetch all faces with group_id
2. Extract 512-dim embeddings
3. Compute cosine distance matrix
4. Run DBSCAN(eps=1-confidence, min_samples=1)
5. Assign person_id to each cluster
6. Update Qdrant with set_payload
```

### person_id Format
```
person_{group_id}_{cluster_number}

Examples:
  person_engagement_photos_1
  person_engagement_photos_2
  person_test_cluster_15
  person_temp_42
```

---

## Next Steps

1. **Monitor clustering progress** via server logs
2. **Verify person_id assignments** in Qdrant
3. **Search using person_id filters** (future enhancement)
4. **Export person clusters** for downstream use
5. **Fine-tune confidence** based on accuracy needs

---

## Troubleshooting

**Issue**: No faces found for group_id  
**Solution**: Ensure you've run `/digest` with the same group_id first

**Issue**: Faces not clustering as expected  
**Solution**: Adjust confidence threshold (try 0.85 or 0.90)

**Issue**: Too many single-face clusters  
**Solution**: Lower confidence (try 0.75 or 0.70)

**Issue**: Very broad clusters (unrelated faces grouped)  
**Solution**: Raise confidence (try 0.90 or 0.95)

---

## API Response Flow

```
Request → API Endpoint → Background Task Started
           ↓
        Job ID Returned (202 Accepted)
           ↓
     Clustering Algorithm Runs
        - Fetch faces
        - Calculate distances
        - Run DBSCAN
        - Update Qdrant
           ↓
      Task Completes
     (Check logs for results)
```
