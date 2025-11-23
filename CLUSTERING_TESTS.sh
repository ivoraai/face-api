#!/bin/bash
# Clustering Feature Test Commands

echo "=== Clustering Feature - Quick Test ==="
echo ""

# Test 1: Cluster with default confidence (0.8)
echo "[1] Cluster with default confidence (0.8)"
echo 'curl -X POST http://localhost:8000/cluster-faces \'
echo "  -H 'Content-Type: application/json' \\"
echo '  -d '"'"'{
echo '    "group_id": "engagement_photos",
echo '    "collection": "face_embeddings",
echo '    "confidence": 0.8
echo '  }'"'"
echo ""

# Test 2: Cluster with strict confidence (0.9)
echo "[2] Cluster with strict confidence (0.9 - fewer, tighter clusters)"
echo 'curl -X POST http://localhost:8000/cluster-faces \'
echo "  -H 'Content-Type: application/json' \\"
echo '  -d '"'"'{
echo '    "group_id": "engagement_photos",
echo '    "collection": "face_embeddings",
echo '    "confidence": 0.9
echo '  }'"'"
echo ""

# Test 3: Cluster with loose confidence (0.7)
echo "[3] Cluster with loose confidence (0.7 - more, broader clusters)"
echo 'curl -X POST http://localhost:8000/cluster-faces \'
echo "  -H 'Content-Type: application/json' \\"
echo '  -d '"'"'{
echo '    "group_id": "engagement_photos",
echo '    "collection": "face_embeddings",
echo '    "confidence": 0.7
echo '  }'"'"
echo ""

# Test 4: Test different group_id
echo "[4] Cluster different group"
echo 'curl -X POST http://localhost:8000/cluster-faces \'
echo "  -H 'Content-Type: application/json' \\"
echo '  -d '"'"'{
echo '    "group_id": "td_photos",
echo '    "collection": "face_embeddings",
echo '    "confidence": 0.85
echo '  }'"'"
echo ""

echo "=== COPY & PASTE THESE COMMANDS ==="
echo ""

# Direct test - confidence 0.8
echo "# Test 1: Basic clustering (confidence 0.8)"
cat << 'EOF'
curl -X POST http://localhost:8000/cluster-faces \
  -H 'Content-Type: application/json' \
  -d '{"group_id": "engagement_photos", "collection": "face_embeddings", "confidence": 0.8}' | jq .
EOF
echo ""

# Confidence 0.9 (strict)
echo "# Test 2: Strict clustering (confidence 0.9)"
cat << 'EOF'
curl -X POST http://localhost:8000/cluster-faces \
  -H 'Content-Type: application/json' \
  -d '{"group_id": "engagement_photos", "collection": "face_embeddings", "confidence": 0.9}' | jq .
EOF
echo ""

# Confidence 0.7 (loose)
echo "# Test 3: Loose clustering (confidence 0.7)"
cat << 'EOF'
curl -X POST http://localhost:8000/cluster-faces \
  -H 'Content-Type: application/json' \
  -d '{"group_id": "engagement_photos", "collection": "face_embeddings", "confidence": 0.7}' | jq .
EOF
echo ""

# Confidence 0.85 (recommended)
echo "# Test 4: Recommended clustering (confidence 0.85)"
cat << 'EOF'
curl -X POST http://localhost:8000/cluster-faces \
  -H 'Content-Type: application/json' \
  -d '{"group_id": "engagement_photos", "collection": "face_embeddings", "confidence": 0.85}' | jq .
EOF
echo ""

echo "=== FULL WORKFLOW TEST ==="
echo ""
echo "Step 1: Digest images (if not already done)"
cat << 'EOF'
curl -X POST http://localhost:8000/digest \
  -H 'Content-Type: application/json' \
  -d '{
    "local_dir_path": "/Users/harshitsmac/Documents/dr/Jiya Maam Engagement/Candid Photo",
    "group_id": "engagement_photos",
    "collection": "face_embeddings",
    "confidence": 0.7,
    "threads": 4,
    "max_retries": 2
  }' | jq .
EOF
echo ""

echo "Step 2: Wait for digest to complete (30-60 seconds)"
echo "  curl -s http://localhost:8000/get-digests | jq '.jobs[0] | {status, progress, faces_processed}'"
echo ""

echo "Step 3: Run clustering with confidence 0.85"
cat << 'EOF'
curl -X POST http://localhost:8000/cluster-faces \
  -H 'Content-Type: application/json' \
  -d '{
    "group_id": "engagement_photos",
    "collection": "face_embeddings",
    "confidence": 0.85
  }' | jq .
EOF
echo ""

echo "Step 4: Verify clustering updated Qdrant"
cat << 'EOF'
python3 << 'PYTHON'
from qdrant_client import QdrantClient
qclient = QdrantClient(host="localhost", port=6333)
points = qclient.scroll("face_embeddings", limit=50, with_payload=True)[0]
person_ids = {}
for p in points:
    pid = p.payload.get('person_id')
    if pid:
        person_ids[pid] = person_ids.get(pid, 0) + 1

print(f"Total points with person_id: {len(person_ids)}")
for pid, count in list(sorted(person_ids.items()))[:10]:
    print(f"  {pid}: {count} faces")
PYTHON
EOF
echo ""

echo "=== CONFIDENCE COMPARISON TEST ==="
echo ""
echo "Run all three at once to compare results:"
echo ""
echo "# Confidence 0.70 (loose - many clusters)"
echo "curl -s -X POST http://localhost:8000/cluster-faces -H 'Content-Type: application/json' -d '{\"group_id\":\"test1\",\"confidence\":0.70}' | jq .job_id"
echo ""
echo "# Confidence 0.85 (balanced - recommended)"
echo "curl -s -X POST http://localhost:8000/cluster-faces -H 'Content-Type: application/json' -d '{\"group_id\":\"test2\",\"confidence\":0.85}' | jq .job_id"
echo ""
echo "# Confidence 0.95 (strict - few clusters)"
echo "curl -s -X POST http://localhost:8000/cluster-faces -H 'Content-Type: application/json' -d '{\"group_id\":\"test3\",\"confidence\":0.95}' | jq .job_id"
echo ""

echo "=== NOTES ==="
echo ""
echo "✓ All /cluster-faces requests return 202 Accepted (background task)"
echo "✓ Job ID returned but results process asynchronously"
echo "✓ Check /tmp/uvicorn.log for clustering progress:"
echo "    tail -f /tmp/uvicorn.log | grep cluster"
echo ""
echo "✓ Confidence parameter:"
echo "    0.7 = loose (more clusters, fewer false negatives)"
echo "    0.8 = default (balanced)"
echo "    0.85 = recommended (good balance)"
echo "    0.9 = strict (fewer clusters, more false positives)"
echo "    0.95 = very strict (only near-perfect matches)"
echo ""
echo "✓ Results: Each face gets person_id: person_{group_id}_{cluster_number}"
echo ""
echo "✓ Use with search:"
echo "    curl -X POST http://localhost:8000/search-face?confidence=0.8 -F 'image=@photo.jpg'"
echo "    (Future: Filter by person_id in results)"
echo ""
