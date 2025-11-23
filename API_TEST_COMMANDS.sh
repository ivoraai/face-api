#!/bin/bash
# Face Service API - Quick Test Commands (Updated with Digest & Search Filters)
# Copy and paste these into your terminal to test each endpoint

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

API_URL="http://localhost:8000"
IMAGE_FILE="im.png"
TEST_DIR="/Users/harshitsmac/Documents/dr/test_digest_images"

echo -e "${BLUE}Face Service API - Quick Test Commands${NC}\n"

# Test 1: Health Check
echo -e "${GREEN}[1] Health Check${NC}"
echo "curl -X GET $API_URL/"
echo ""

# Test 2: Get Faces
echo -e "${GREEN}[2] Extract Faces${NC}"
echo "curl -X POST $API_URL/get-faces \\"
echo "  -F \"image=@$IMAGE_FILE\" | jq ."
echo ""

# Test 3: Get Features
echo -e "${GREEN}[3] Extract Features (age, gender, emotion)${NC}"
echo "curl -X POST $API_URL/get-features \\"
echo "  -F \"image=@$IMAGE_FILE\" | jq '.faces[0].features'"
echo ""

# Test 4: Get Embedding
echo -e "${GREEN}[4] Extract Embeddings (512-dimensional vectors)${NC}"
echo "curl -X POST $API_URL/get-embedding \\"
echo "  -F \"image=@$IMAGE_FILE\" | jq '.faces[0] | {face_id, embedding_length: (.embedding | length), has_thumbnail: (.face_b64 != null)}'"
echo ""

# ================================
# SEARCH ENDPOINT (WITH FILTERS)
# ================================

# Test 5a: Search without filters
echo -e "${GREEN}[5a] Search Similar Faces (all)${NC}"
echo "curl -X POST \"$API_URL/search-face?confidence=0.8&limit=5\" \\"
echo "  -F \"image=@$IMAGE_FILE\" | jq '.search_results'"
echo ""

# Test 5b: Search with group_id filter
echo -e "${GREEN}[5b] Search within Specific Group${NC}"
echo "curl -X POST \"$API_URL/search-face?group_id=engagement_photos&confidence=0.8&limit=5\" \\"
echo "  -F \"image=@$IMAGE_FILE\" | jq '.search_results'"
echo ""

# Test 5c: Search with collection filter
echo -e "${GREEN}[5c] Search in Specific Collection${NC}"
echo "curl -X POST \"$API_URL/search-face?collection_name=face_embeddings&confidence=0.8&limit=5\" \\"
echo "  -F \"image=@$IMAGE_FILE\" | jq '.search_results'"
echo ""

# Test 5d: Search with both filters
echo -e "${GREEN}[5d] Search with Collection + Group Filter${NC}"
echo "curl -X POST \"$API_URL/search-face?collection_name=face_embeddings&group_id=engagement_photos&confidence=0.8&limit=5\" \\"
echo "  -F \"image=@$IMAGE_FILE\" | jq '.search_results'"
echo ""

# ================================
# DIGEST ENDPOINT (WITH COLLECTION)
# ================================

# Test 6a: Digest with local directory
echo -e "${GREEN}[6a] Start Digest Job (Local Directory)${NC}"
echo "curl -X POST $API_URL/digest \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{
echo "    \"local_dir_path\": \"$TEST_DIR\","
echo "    \"group_id\": \"engagement_photos\","
echo "    \"collection\": \"face_embeddings\","
echo "    \"confidence\": 0.7,"
echo "    \"threads\": 4"
echo "  }' | jq ."
echo ""

# Test 6b: Digest with S3
echo -e "${GREEN}[6b] Start Digest Job (S3)${NC}"
echo "curl -X POST $API_URL/digest \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{
echo "    \"s3_bucket\": \"my-bucket\","
echo "    \"s3_prefix\": \"faces/\","
echo "    \"group_id\": \"s3_group\","
echo "    \"collection\": \"face_embeddings\","
echo "    \"confidence\": 0.7,"
echo "    \"threads\": 2"
echo "  }' | jq ."
echo ""

# Test 6c: Get all digests
echo -e "${GREEN}[6c] Get All Active Digests${NC}"
echo "curl -X GET $API_URL/get-digests | jq '.jobs'"
echo ""

# Test 6d: Get specific digest
echo -e "${GREEN}[6d] Get Specific Digest Status${NC}"
echo "curl -X GET $API_URL/get-digests/{JOB_ID} | jq ."
echo ""

# Test 7: Cluster Faces
echo -e "${GREEN}[7] Start Clustering Job${NC}"
echo "curl -X POST $API_URL/cluster-faces \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"group_id\": \"engagement_photos\", \"collection\": \"face_embeddings\", \"confidence\": 0.8}' | jq ."
echo ""

# Batch Test: Run all at once
echo -e "${BLUE}BATCH TEST - Copy this to run all tests at once:${NC}\n"
echo "#!/bin/bash"
echo "echo '=== Test 1: Health Check ==='"
echo "curl -s $API_URL/ | jq ."
echo ""
echo "echo '=== Test 2: Get Faces ==='"
echo "curl -s -X POST $API_URL/get-faces -F 'image=@$IMAGE_FILE' | jq '.faces | length'"
echo ""
echo "echo '=== Test 3: Get Features ==='"
echo "curl -s -X POST $API_URL/get-features -F 'image=@$IMAGE_FILE' | jq '.faces[0].features'"
echo ""
echo "echo '=== Test 4: Get Embedding ==='"
echo "curl -s -X POST $API_URL/get-embedding -F 'image=@$IMAGE_FILE' | jq '.faces[0] | {face_id, embedding_len: (.embedding | length)}'"
echo ""
echo "echo '=== Test 5: Search ==='"
echo "curl -s -X POST \"$API_URL/search-face?confidence=0.8&group_id=engagement_photos\" -F 'image=@$IMAGE_FILE' | jq '.search_results | length'"
echo ""
echo "echo '=== Test 6a: Digest (Local) ==='"
echo "curl -s -X POST $API_URL/digest -H 'Content-Type: application/json' -d '{\"local_dir_path\":\"$TEST_DIR\",\"group_id\":\"e1\",\"collection\":\"face_embeddings\",\"threads\":4}' | jq .job_id"
echo ""
echo "echo '=== Test 6b: Get Digests ==='"
echo "curl -s -X GET $API_URL/get-digests | jq '.jobs | length'"
echo ""
echo "echo '=== Test 7: Cluster ==='"
echo "curl -s -X POST http://localhost:8000/cluster-faces -H 'Content-Type: application/json' -d '{\"group_id\":\"e1\",\"collection\":\"face_embeddings\",\"confidence\":0.8}' | jq .job_id"
echo ""

# ================================
# QUICK REFERENCE - ALL CURLS
# ================================

echo -e "\n${BLUE}=== QUICK REFERENCE - ONE-LINERS ===${NC}\n"

echo -e "${GREEN}[1] Health:${NC}"
echo "curl http://localhost:8000/"
echo ""

echo -e "${GREEN}[2] Get Faces:${NC}"
echo "curl -X POST http://localhost:8000/get-faces -F \"image=@im.png\""
echo ""

echo -e "${GREEN}[3] Get Features:${NC}"
echo "curl -X POST http://localhost:8000/get-features -F \"image=@im.png\""
echo ""

echo -e "${GREEN}[4] Get Embedding:${NC}"
echo "curl -X POST http://localhost:8000/get-embedding -F \"image=@im.png\""
echo ""

echo -e "${GREEN}[5a] Search (all):${NC}"
echo "curl -X POST \"http://localhost:8000/search-face?confidence=0.8\" -F \"image=@im.png\""
echo ""

echo -e "${GREEN}[5b] Search (by group):${NC}"
echo "curl -X POST \"http://localhost:8000/search-face?group_id=engagement_photos&confidence=0.8\" -F \"image=@im.png\""
echo ""

echo -e "${GREEN}[5c] Search (by collection):{{NC}"
echo "curl -X POST \"http://localhost:8000/search-face?collection_name=face_embeddings&confidence=0.8\" -F \"image=@im.png\""
echo ""

echo -e "${GREEN}[5d] Search (collection + group):${NC}"
echo "curl -X POST \"http://localhost:8000/search-face?collection_name=face_embeddings&group_id=engagement_photos&confidence=0.8\" -F \"image=@im.png\""
echo ""

echo -e "${GREEN}[6a] Digest (local):${NC}"
echo "curl -X POST http://localhost:8000/digest -H 'Content-Type: application/json' -d '{\"local_dir_path\": \"$TEST_DIR\", \"group_id\": \"event1\", \"collection\": \"face_embeddings\", \"confidence\": 0.7, \"threads\": 4}'"
echo ""

echo -e "${GREEN}[6b] Digest (S3):${NC}"
echo "curl -X POST http://localhost:8000/digest -H 'Content-Type: application/json' -d '{\"s3_bucket\": \"my-bucket\", \"s3_prefix\": \"faces/\", \"group_id\": \"s3_event\", \"collection\": \"face_embeddings\", \"threads\": 2}'"
echo ""

echo -e "${GREEN}[6c] Get All Digests:${NC}"
echo "curl http://localhost:8000/get-digests"
echo ""

echo -e "${GREEN}[6d] Get Digest by Job ID:${NC}"
echo "curl http://localhost:8000/get-digests/digest-<JOB_ID>"
echo ""

echo -e "${GREEN}[7] Cluster:${NC}"
echo "curl -X POST http://localhost:8000/cluster-faces -H 'Content-Type: application/json' -d '{\"group_id\": \"event1\", \"collection\": \"face_embeddings\", \"confidence\": 0.8}'"
echo ""

# ================================
# PAYLOAD EXAMPLES
# ================================

echo -e "\n${BLUE}=== PAYLOAD EXAMPLES ===${NC}\n"

echo -e "${GREEN}Digest Request (Local Directory):${NC}"
cat << 'EOF'
{
  "local_dir_path": "/Users/harshitsmac/Documents/dr/test_digest_images",
  "group_id": "engagement_photos",
  "collection": "face_embeddings",
  "confidence": 0.7,
  "threads": 4
}
EOF
echo ""

echo -e "${GREEN}Digest Request (S3):${NC}"
cat << 'EOF'
{
  "s3_bucket": "my-bucket",
  "s3_prefix": "faces/",
  "group_id": "s3_images",
  "collection": "face_embeddings",
  "confidence": 0.7,
  "threads": 4
}
EOF
echo ""

echo -e "${GREEN}Digest Response:${NC}"
cat << 'EOF'
{
  "job_id": "digest-12345abc...",
  "status": "queued",
  "message": "Digest task queued for processing"
}
EOF
echo ""

echo -e "${GREEN}Digest Status Response:${NC}"
cat << 'EOF'
{
  "job_id": "digest-12345abc...",
  "group_id": "engagement_photos",
  "status": "processing",
  "progress": 75,
  "faces_processed": 12,
  "total_images": 16,
  "matched_faces": 0,
  "collection": "face_embeddings",
  "source": "/Users/harshitsmac/Documents/dr/test_digest_images",
  "confidence": 0.7,
  "threads": 4,
  "start_time": "2025-11-23T10:45:30.123456",
  "end_time": null,
  "error_message": null,
  "upserted_ids": ["id1", "id2", "id3", ...]
}
EOF
echo ""

echo -e "${GREEN}Get All Digests Response:${NC}"
cat << 'EOF'
{
  "total_jobs": 2,
  "jobs": [
    {
      "job_id": "digest-abc123...",
      "group_id": "engagement_photos",
      "status": "completed",
      "progress": 100,
      "faces_processed": 15,
      "total_images": 16,
      "collection": "face_embeddings",
      "source": "/Users/harshitsmac/Documents/dr/test_digest_images",
      "confidence": 0.7,
      "threads": 4,
      "start_time": "2025-11-23T10:45:00",
      "end_time": "2025-11-23T10:46:30",
      "error_message": null
    },
    {
      "job_id": "digest-def456...",
      "group_id": "s3_images",
      "status": "processing",
      "progress": 50,
      "faces_processed": 8,
      "total_images": 20,
      "collection": "face_embeddings",
      "source": "s3://my-bucket/faces/",
      "confidence": 0.7,
      "threads": 4,
      "start_time": "2025-11-23T10:45:30",
      "end_time": null,
      "error_message": null
    }
  ]
}
EOF
echo ""

echo -e "${YELLOW}=== NOTES ===${NC}"
echo "- Digest: use EITHER local_dir_path OR (s3_bucket + s3_prefix)"
echo "- collection field: Qdrant collection to upsert faces into"
echo "- Search can filter by collection_name and/or group_id"
echo "- total_images: number of image files found"
echo "- faces_processed: number of faces actually extracted and upserted"
echo "- Status: queued → processing → completed (or failed)"
echo ""

# Pretty print with jq
echo -e "\n${BLUE}INSTALL jq FOR PRETTY JSON OUTPUT:${NC}"
echo "brew install jq  # macOS"
echo "apt-get install jq  # Ubuntu/Debian"
echo ""

# Python test script
echo -e "${BLUE}PYTHON TEST SCRIPT:${NC}\n"
cat << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
import requests
import json

API_URL = "http://localhost:8000"
IMAGE_FILE = "im.png"

def test_endpoint(method, endpoint, **kwargs):
    url = f"{API_URL}{endpoint}"
    try:
        if method == "GET":
            r = requests.get(url)
        elif method == "POST_FILE":
            with open(IMAGE_FILE, 'rb') as f:
                r = requests.post(url, files={'image': f}, params=kwargs.get('params'))
        elif method == "POST_JSON":
            r = requests.post(url, json=kwargs.get('json'), headers={'Content-Type': 'application/json'})
        
        print(f"✓ {endpoint}")
        print(f"  Status: {r.status_code}")
        return r.json()
    except Exception as e:
        print(f"✗ {endpoint}: {e}")
        return None

print("Testing Face Service API...\n")

# Test each endpoint
test_endpoint("GET", "/")
resp = test_endpoint("POST_FILE", "/get-faces")
if resp and resp.get('faces'):
    print(f"  Faces found: {len(resp['faces'])}")

resp = test_endpoint("POST_FILE", "/get-features")
if resp and resp.get('faces'):
    features = resp['faces'][0].get('features', {})
    print(f"  Features: age={features.get('age')}, gender={features.get('gender')}, emotion={features.get('emotion')}")

resp = test_endpoint("POST_FILE", "/get-embedding")
if resp and resp.get('faces'):
    emb_len = len(resp['faces'][0].get('embedding', []))
    print(f"  Embedding length: {emb_len}")

test_endpoint("POST_FILE", "/search-face", params={'confidence': 0.8, 'limit': 5})
test_endpoint("POST_JSON", "/digest", json={"s3_bucket": "test", "s3_prefix": "faces/", "group_id": "g1"})
test_endpoint("POST_JSON", "/cluster-faces", json={"group_id": "g1"})

print("\n✓ All tests completed!")
PYTHON_SCRIPT

echo ""
echo -e "${BLUE}To run the Python script:${NC}"
echo "python3 test_api.py"
