#!/bin/bash

# Digest Endpoint Quick Test Script
# Tests all digest functionality with curl commands

set -e

API_URL="http://localhost:8000"
TEST_DIR="/Users/harshitsmac/Documents/dr/test_digest_images"

echo "🔍 Face Service - Digest Endpoint Tests"
echo "=========================================="
echo ""

# Test 1: Health check
echo "✓ Test 1: Health Check"
curl -s $API_URL/ | jq -c '{service, status}' || echo "Server not running!"
echo ""

# Test 2: Start digest job
echo "✓ Test 2: Start Digest Job"
JOB_ID=$(curl -s -X POST $API_URL/digest \
  -H "Content-Type: application/json" \
  -d "{
    \"local_dir_path\": \"$TEST_DIR\",
    \"group_id\": \"digest_test_$(date +%s)\",
    \"confidence\": 0.7,
    \"threads\": 2
  }" | jq -r '.job_id')
echo "Job ID: $JOB_ID"
echo ""

# Test 3: Check status immediately
echo "✓ Test 3: Check Status (should be processing or queued)"
curl -s $API_URL/get-digests/$JOB_ID | jq '{status, progress, faces_processed}'
echo ""

# Test 4: Wait and check again
echo "✓ Test 4: Wait 5 seconds and check final status"
sleep 5
curl -s $API_URL/get-digests/$JOB_ID | jq '{job_id, status, progress, faces_processed, total_faces, threads, end_time}'
echo ""

# Test 5: Get all digest jobs
echo "✓ Test 5: List All Digest Jobs"
curl -s $API_URL/get-digests | jq '.jobs | length' | xargs echo "Total jobs:"
curl -s $API_URL/get-digests | jq '.jobs[] | {job_id, group_id, status, progress, faces_processed}'
echo ""

# Test 6: Error handling - invalid job ID
echo "✓ Test 6: Error Handling - Invalid Job ID"
curl -s $API_URL/get-digests/invalid-job-id | jq '.' || echo "Expected 404 error"
echo ""

# Test 7: Error handling - missing required field
echo "✓ Test 7: Error Handling - Missing Required Path"
curl -s -X POST $API_URL/digest \
  -H "Content-Type: application/json" \
  -d '{"group_id": "test", "confidence": 0.7}' | jq '.detail[0].msg' || true
echo ""

# Test 8: Verify faces are searchable
echo "✓ Test 8: Search Digested Faces"
GROUP_ID=$(curl -s $API_URL/get-digests/$JOB_ID | jq -r '.group_id')
echo "Searching with group_id: $GROUP_ID"
RESULTS=$(curl -s -X POST $API_URL/search-face \
  -H "Content-Type: multipart/form-data" \
  -F "image=@$TEST_DIR/im.png" \
  -F "group_id=$GROUP_ID" \
  -F "confidence=0.5")
echo $RESULTS | jq '.faces_detected' | xargs echo "Faces detected:"
echo $RESULTS | jq '.search_results[0].matches_found' | xargs echo "Matches found:"
echo ""

echo "✅ All tests completed!"
