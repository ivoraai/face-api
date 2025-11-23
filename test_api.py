#!/usr/bin/env python3
"""
Face Service API - Comprehensive Test Script
Tests all 7 endpoints with detailed output
"""

import requests
import json
import sys
from pathlib import Path

API_URL = "http://localhost:8000"
IMAGE_FILE = "im.png"

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

def print_test(name):
    print(f"{Colors.OKCYAN}[TEST] {name}{Colors.ENDC}")

def print_success(msg):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")

def print_info(msg):
    print(f"{Colors.OKBLUE}ℹ {msg}{Colors.ENDC}")

def test_health_check():
    """Test: GET / - Health Check"""
    print_test("GET / - Health Check")
    try:
        r = requests.get(f"{API_URL}/")
        if r.status_code == 200:
            data = r.json()
            print_success(f"Status: {r.status_code}")
            print_info(f"Service: {data.get('service')}")
            print_info(f"Status: {data.get('status')}")
            print_info(f"Collection: {data.get('qdrant_collection')}")
            return True
        else:
            print_error(f"Status: {r.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_get_faces():
    """Test: POST /get-faces - Extract Faces"""
    print_test("POST /get-faces - Extract Faces")
    try:
        with open(IMAGE_FILE, 'rb') as f:
            r = requests.post(f"{API_URL}/get-faces", files={'image': f})
        
        if r.status_code == 200:
            data = r.json()
            faces = data.get('faces', [])
            print_success(f"Status: {r.status_code}")
            print_info(f"Faces detected: {len(faces)}")
            
            if faces:
                face = faces[0]
                print_info(f"  - Face ID: {face['face_id']}")
                print_info(f"  - Confidence: {face['confidence']:.4f}")
                print_info(f"  - Location: ({face['facial_area']['x']}, {face['facial_area']['y']}, {face['facial_area']['w']}x{face['facial_area']['h']})")
                print_info(f"  - Thumbnail: {len(face.get('face_b64', '')) // 1000}KB base64")
            return True
        else:
            print_error(f"Status: {r.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_get_features():
    """Test: POST /get-features - Extract Features"""
    print_test("POST /get-features - Extract Features (Age, Gender, Emotion)")
    try:
        with open(IMAGE_FILE, 'rb') as f:
            r = requests.post(f"{API_URL}/get-features", files={'image': f})
        
        if r.status_code == 200:
            data = r.json()
            faces = data.get('faces', [])
            print_success(f"Status: {r.status_code}")
            print_info(f"Faces processed: {len(faces)}")
            
            if faces:
                face = faces[0]
                features = face.get('features', {})
                print_info(f"  - Emotion: {features.get('emotion', 'N/A')}")
                print_info(f"  - Age: {features.get('age', 'N/A')} years")
                print_info(f"  - Gender: {features.get('gender', 'N/A')}")
                if features.get('landmarks'):
                    print_info(f"  - Landmarks: {features['landmarks']}")
            return True
        else:
            print_error(f"Status: {r.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_get_embedding():
    """Test: POST /get-embedding - Extract Embeddings"""
    print_test("POST /get-embedding - Extract Face Embeddings (512-dim)")
    try:
        with open(IMAGE_FILE, 'rb') as f:
            r = requests.post(f"{API_URL}/get-embedding", files={'image': f})
        
        if r.status_code == 200:
            data = r.json()
            faces = data.get('faces', [])
            print_success(f"Status: {r.status_code}")
            print_info(f"Faces processed: {len(faces)}")
            
            if faces:
                face = faces[0]
                embedding = face.get('embedding', [])
                features = face.get('features', {})
                print_info(f"  - Embedding dimension: {len(embedding)}")
                print_info(f"  - First 5 values: {[f'{v:.6f}' for v in embedding[:5]]}")
                print_info(f"  - Thumbnail: {len(face.get('face_b64', '')) // 1000}KB base64")
                print_info(f"  - Features: {features.get('emotion')} (age {features.get('age')}, {features.get('gender')})")
            return True
        else:
            print_error(f"Status: {r.status_code}")
            print_error(f"Response: {r.text[:200]}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_search_face():
    """Test: POST /search-face - Search Similar Faces"""
    print_test("POST /search-face - Search Similar Faces in Qdrant")
    try:
        with open(IMAGE_FILE, 'rb') as f:
            r = requests.post(f"{API_URL}/search-face?confidence=0.8&limit=5", files={'image': f})
        
        if r.status_code == 200:
            data = r.json()
            matches = data.get('matches', [])
            print_success(f"Status: {r.status_code}")
            print_info(f"Similar faces found: {len(matches)}")
            
            if matches:
                for i, match in enumerate(matches[:3]):
                    print_info(f"  Match {i+1}:")
                    print_info(f"    - S3 Path: {match.get('image_s3_path')}")
                    print_info(f"    - Similarity: {match.get('similarity_score'):.4f}")
                    print_info(f"    - Person ID: {match.get('person_id')}")
            else:
                print_info("  (Note: Qdrant is empty - populate with /digest endpoint)")
            return True
        else:
            print_error(f"Status: {r.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_digest():
    """Test: POST /digest - Start Digest Job"""
    print_test("POST /digest - Start S3 Digest Job")
    try:
        payload = {
            "s3_bucket": "test-bucket",
            "s3_prefix": "faces/",
            "group_id": "group-123"
        }
        r = requests.post(f"{API_URL}/digest", json=payload)
        
        if r.status_code == 202:
            data = r.json()
            print_success(f"Status: {r.status_code} (Accepted)")
            print_info(f"Job ID: {data.get('job_id')}")
            print_info(f"Status: {data.get('status')}")
            print_info(f"Message: {data.get('message')}")
            return True
        else:
            print_error(f"Status: {r.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_cluster_faces():
    """Test: POST /cluster-faces - Start Clustering Job"""
    print_test("POST /cluster-faces - Start Clustering Job")
    try:
        payload = {"group_id": "group-123"}
        r = requests.post(f"{API_URL}/cluster-faces", json=payload)
        
        if r.status_code == 202:
            data = r.json()
            print_success(f"Status: {r.status_code} (Accepted)")
            print_info(f"Job ID: {data.get('job_id')}")
            print_info(f"Status: {data.get('status')}")
            print_info(f"Message: {data.get('message')}")
            return True
        else:
            print_error(f"Status: {r.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def main():
    print_header("Face Service API - Comprehensive Test Suite")
    
    # Check if server is running
    print_test("Checking server connectivity...")
    try:
        requests.get(f"{API_URL}/", timeout=2)
        print_success(f"Server is running at {API_URL}")
    except requests.exceptions.ConnectionError:
        print_error(f"Cannot connect to {API_URL}")
        print_info("Start the server with: uvicorn face_service_fastapi:app --reload --host 0.0.0.0 --port 8000")
        sys.exit(1)
    
    # Check if image exists
    if not Path(IMAGE_FILE).exists():
        print_error(f"Image file not found: {IMAGE_FILE}")
        print_info(f"Create a test image or use: im.png")
        sys.exit(1)
    
    print_success(f"Using image: {IMAGE_FILE}\n")
    
    # Run tests
    tests = [
        ("Health Check", test_health_check),
        ("Get Faces", test_get_faces),
        ("Get Features", test_get_features),
        ("Get Embedding", test_get_embedding),
        ("Search Face", test_search_face),
        ("Digest Job", test_digest),
        ("Cluster Faces", test_cluster_faces),
    ]
    
    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{Colors.OKGREEN}✓ PASS{Colors.ENDC}" if result else f"{Colors.FAIL}✗ FAIL{Colors.ENDC}"
        print(f"{status} - {name}")
    
    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.ENDC}")
    
    if passed == total:
        print(f"{Colors.OKGREEN}{Colors.BOLD}🎉 ALL TESTS PASSED!{Colors.ENDC}")
        return 0
    else:
        print(f"{Colors.WARNING}{Colors.BOLD}⚠️  Some tests failed{Colors.ENDC}")
        return 1

if __name__ == "__main__":
    exit(main())
