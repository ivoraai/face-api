"""
face_service_fastapi.py

Single-file FastAPI service that implements the endpoints you requested:
 - POST /get-faces
 - POST /get-features
 - POST /get-embedding
 - POST /search-face
 - POST /digest
 - POST /cluster-faces

Features:
 - Uses DeepFace (RetinaFace + ArcFace) for detection and embeddings
 - Uses Qdrant for upsert/search
 - Optional Celery integration if CELERY_BROKER_URL is provided; falls back to FastAPI BackgroundTasks
 - Returns cropped face thumbnails as base64, features, embeddings, and search matches

Environment variables (via .env or environment):
 QDRANT_URL (default: localhost)
 QDRANT_PORT (default: 6333)
 QDRANT_API_KEY (optional)
 QDRANT_COLLECTION (default: face_embeddings)
 CELERY_BROKER_URL (optional, e.g. redis://localhost:6379/0)
 CELERY_RESULT_BACKEND (optional)

Dependencies (pip):
 fastapi uvicorn python-multipart deepface qdrant-client python-dotenv pillow numpy opencv-python celery[redis]

Run (development):
 uvicorn face_service_fastapi:app --reload --host 0.0.0.0 --port 8000

If using Celery for background jobs (digest/cluster), run a worker:
 celery -A face_service_fastapi.celery_app worker --loglevel=info

"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
from dotenv import load_dotenv
import cv2
import numpy as np
import base64
from io import BytesIO
from PIL import Image, ImageOps
import uuid
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from deepface import DeepFace
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances
from google.cloud import storage
from google.oauth2 import service_account
import io

# Optional Celery
try:
    from celery import Celery
    CELERY_AVAILABLE = True
except Exception:
    CELERY_AVAILABLE = False

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "face_embeddings")
EMBEDDING_SIZE = int(os.getenv("EMBEDDING_SIZE", "512"))

# Celery config (optional)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")

app = FastAPI(title="Face Worker Service")

# Setup Qdrant client
if QDRANT_API_KEY:
    qclient = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
else:
    qclient = QdrantClient(host=QDRANT_URL, port=QDRANT_PORT)

# Ensure collection exists
try:
    qclient.get_collection(QDRANT_COLLECTION)
except Exception:
    qclient.create_collection(collection_name=QDRANT_COLLECTION,
                              vectors_config=VectorParams(size=EMBEDDING_SIZE, distance=Distance.COSINE))

# Global job tracking systems
ACTIVE_DIGESTS: Dict[str, Dict[str, Any]] = {}
ACTIVE_CLUSTERS: Dict[str, Dict[str, Any]] = {}  # Cluster processes tracking

# Setup Celery if available and broker set
celery_app = None
if CELERY_AVAILABLE and CELERY_BROKER_URL:
    celery_app = Celery("face_tasks", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

# Helpers

def read_imagefile(file_bytes: bytes) -> np.ndarray:
    nparr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img


def crop_and_b64(img: np.ndarray, area: Dict[str, int]) -> str:
    x, y, w, h = area['x'], area['y'], area['w'], area['h']
    face = img[y:y+h, x:x+w]
    # Resize to at most 512x512 keeping aspect ratio
    face_pil = Image.fromarray(cv2.cvtColor(face, cv2.COLOR_BGR2RGB))
    face_pil.thumbnail((512, 512))
    buf = BytesIO()
    face_pil.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return b64


def extract_faces_from_image(img: np.ndarray, detector_backend: str = 'retinaface') -> List[Dict[str, Any]]:
    """Return list of face objects from DeepFace.extract_faces-compatible structure"""
    # DeepFace.extract_faces expects a path or np array; return list of dicts with 'facial_area' and 'confidence' and 'face'
    # We'll call DeepFace.extract_faces directly with numpy array
    try:
        face_objs = DeepFace.extract_faces(img_path=img,
                                           detector_backend=detector_backend,
                                           enforce_detection=True,
                                           align=True)
    except Exception as e:
        # If enforce_detection True fails, return empty list
        try:
            face_objs = DeepFace.extract_faces(img_path=img,
                                               detector_backend=detector_backend,
                                               enforce_detection=False,
                                               align=True)
        except Exception as e2:
            raise RuntimeError(f"Face extraction failed: {e2}")

    return face_objs


def get_embedding_from_face(face_img: np.ndarray) -> List[float]:
    # DeepFace.represent returns list of dicts with 'embedding'
    try:
        rep = DeepFace.represent(img_path=face_img, model_name='ArcFace', enforce_detection=False, detector_backend='skip')
        embedding = np.array(rep[0]['embedding']).tolist()
        return embedding
    except Exception as e:
        raise RuntimeError(f"Embedding generation failed: {e}")


# Google Cloud Storage Helper Functions

def init_gcs_client(service_account_path: str = 'sa.json'):
    """
    Initialize GCS client using service account JSON.
    Supports both file-based (local) and environment-based (Cloud Run) credentials.
    """
    try:
        # Try to use service account file if it exists (local development)
        if os.path.exists(service_account_path):
            credentials = service_account.Credentials.from_service_account_file(service_account_path)
            client = storage.Client(credentials=credentials, project=credentials.project_id)
            return client

        # Fall back to environment-based credentials (Cloud Run)
        # This will use GOOGLE_APPLICATION_CREDENTIALS env var or default service account
        client = storage.Client()
        return client
    except Exception as e:
        raise RuntimeError(f"Failed to initialize GCS client: {e}")


def list_gcs_images(bucket_name: str, prefix: str = '', client: storage.Client = None) -> List[storage.Blob]:
    """List all image files from GCS bucket, excluding thumbnail directory"""
    if client is None:
        client = init_gcs_client()

    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix=prefix)

    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp')
    image_blobs = []

    for blob in blobs:
        # Skip thumbnail directory
        if '/thumbnail/' in blob.name or blob.name.startswith('thumbnail/'):
            continue

        # Only include image files
        if blob.name.lower().endswith(image_extensions):
            image_blobs.append(blob)

    return image_blobs


def download_gcs_image(blob: storage.Blob) -> np.ndarray:
    """Download image from GCS and return as numpy array"""
    try:
        image_bytes = blob.download_as_bytes()
        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        raise RuntimeError(f"Failed to download image from GCS: {e}")


def create_thumbnail_from_image(img: np.ndarray, max_size: tuple = (1000, 1000)) -> bytes:
    """Create thumbnail from image maintaining aspect ratio (based on create_thumbnail.py logic)"""
    try:
        # Convert BGR to RGB
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)

        # Fix EXIF orientation
        pil_img = ImageOps.exif_transpose(pil_img)

        # Convert RGBA/LA/P to RGB for JPEG compatibility
        if pil_img.mode in ('RGBA', 'LA', 'P'):
            rgb_img = Image.new('RGB', pil_img.size, (255, 255, 255))
            if pil_img.mode == 'P':
                pil_img = pil_img.convert('RGBA')
            if pil_img.mode in ('RGBA', 'LA'):
                rgb_img.paste(pil_img, mask=pil_img.split()[-1])
            else:
                rgb_img.paste(pil_img)
            pil_img = rgb_img

        # Create thumbnail maintaining aspect ratio
        pil_img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Convert to bytes
        buf = BytesIO()
        pil_img.save(buf, format='JPEG', quality=90, optimize=True)
        return buf.getvalue()
    except Exception as e:
        raise RuntimeError(f"Failed to create thumbnail: {e}")


def upload_thumbnail_to_gcs(thumbnail_bytes: bytes, original_blob_name: str, bucket, blob_name: str = None) -> str:
    """Upload thumbnail to GCS in thumbnail directory, preserving directory structure"""
    try:
        # Create thumbnail path (preserve directory structure)
        # e.g., "photos/image.jpg" -> "thumbnail/photos/image.jpg"
        if blob_name is None:
            blob_name = f"thumbnail/{original_blob_name}"

        thumbnail_blob = bucket.blob(blob_name)
        thumbnail_blob.upload_from_string(
            thumbnail_bytes,
            content_type='image/jpeg'
        )

        # Return the GCS URI
        return f"gs://{bucket.name}/{blob_name}"
    except Exception as e:
        raise RuntimeError(f"Failed to upload thumbnail to GCS: {e}")


# Pydantic response models (minimal)
class FacialArea(BaseModel):
    x: int
    y: int
    w: int
    h: int

class FaceOut(BaseModel):
    face_id: int
    face_b64: Optional[str] = None
    facial_area: FacialArea
    confidence: float

class FeatureFaceOut(BaseModel):
    face_id: int
    facial_area: FacialArea
    confidence: float
    features: Dict[str, Any]

class EmbeddingFaceOut(BaseModel):
    face_id: int
    face_b64: Optional[str] = None
    facial_area: FacialArea
    features: Optional[Dict[str, Any]] = None
    embedding: List[float]

# --- Endpoints ---

@app.post('/get-faces', response_model=Dict[str, List[FaceOut]])
async def get_faces(image: UploadFile = File(...)):
    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail='No image provided')

    img = read_imagefile(contents)
    if img is None:
        raise HTTPException(status_code=400, detail='Invalid image file')

    try:
        face_objs = extract_faces_from_image(img, detector_backend='retinaface')
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    faces_out = []
    for idx, fo in enumerate(face_objs):
        area = fo['facial_area']
        confidence = float(fo.get('confidence', 1.0))
        face_b64 = crop_and_b64(img, area)
        faces_out.append(FaceOut(face_id=idx, face_b64=face_b64, facial_area=area, confidence=confidence))

    return {"faces": faces_out}


@app.post('/get-features', response_model=Dict[str, List[FeatureFaceOut]])
async def get_features(image: UploadFile = File(...)):
    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail='No image provided')

    img = read_imagefile(contents)
    if img is None:
        raise HTTPException(status_code=400, detail='Invalid image file')

    try:
        face_objs = extract_faces_from_image(img, detector_backend='retinaface')
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    faces_out = []
    for idx, fo in enumerate(face_objs):
        area = fo['facial_area']
        confidence = float(fo.get('confidence', 1.0))

        # DeepFace.analyze can give age, gender, emotion and landmarks
        try:
            # analyze expects face image or full image with detector; we'll pass the cropped face
            x, y, w, h = area['x'], area['y'], area['w'], area['h']
            face_crop = img[y:y+h, x:x+w]
            analysis_result = DeepFace.analyze(img_path=face_crop, actions=['age', 'gender', 'emotion'], enforce_detection=False, detector_backend='skip')
            
            # DeepFace.analyze returns a list; take the first result
            analysis = analysis_result[0] if isinstance(analysis_result, list) and analysis_result else {}

            landmarks = None
            if isinstance(analysis, dict) and 'region' in analysis:
                landmarks = analysis.get('region', None)

            features = {
                'emotion': analysis.get('dominant_emotion') if isinstance(analysis, dict) else None,
                'age': int(analysis.get('age')) if isinstance(analysis, dict) and analysis.get('age') is not None else None,
                'gender': analysis.get('dominant_gender') if isinstance(analysis, dict) else None,
                'landmarks': landmarks
            }

        except Exception as e:
            features = {'error': f'feature extraction failed: {e}'}

        faces_out.append(FeatureFaceOut(face_id=idx, facial_area=area, confidence=confidence, features=features))

    return {"faces": faces_out}


@app.post('/get-embedding', response_model=Dict[str, List[EmbeddingFaceOut]])
async def get_embedding(image: UploadFile = File(...)):
    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail='No image provided')

    img = read_imagefile(contents)
    if img is None:
        raise HTTPException(status_code=400, detail='Invalid image file')

    try:
        face_objs = extract_faces_from_image(img, detector_backend='retinaface')
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    faces_out = []
    for idx, fo in enumerate(face_objs):
        area = fo['facial_area']
        confidence = float(fo.get('confidence', 1.0))
        x, y, w, h = area['x'], area['y'], area['w'], area['h']
        face_crop = img[y:y+h, x:x+w]

        # thumbnail
        face_b64 = crop_and_b64(img, area)

        # features
        try:
            analysis_result = DeepFace.analyze(img_path=face_crop, actions=['age', 'gender', 'emotion'], enforce_detection=False, detector_backend='skip')
            # DeepFace.analyze returns a list; take the first result
            analysis = analysis_result[0] if isinstance(analysis_result, list) and analysis_result else {}
            
            features = {
                'emotion': analysis.get('dominant_emotion') if isinstance(analysis, dict) else None,
                'age': int(analysis.get('age')) if isinstance(analysis, dict) and analysis.get('age') is not None else None,
                'gender': analysis.get('dominant_gender') if isinstance(analysis, dict) else None,
                'landmarks': analysis.get('region', None) if isinstance(analysis, dict) else None
            }
        except Exception:
            features = None

        # embedding
        try:
            embedding = get_embedding_from_face(face_crop)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        faces_out.append(EmbeddingFaceOut(face_id=idx, face_b64=face_b64, facial_area=area, features=features, embedding=embedding))

    return {"faces": faces_out}


@app.post('/search-face')
async def search_face(image: UploadFile = File(...), collection_name: str = QDRANT_COLLECTION, 
                      group_id: Optional[str] = None, confidence: float = 0.8, limit: int = 5):
    """
    Search for similar faces in the image across Qdrant database.
    
    Enhanced version that:
    - Detects ALL faces in the image (not just first)
    - Returns richer metadata (facial area, confidence, person_id)
    - Gracefully handles empty Qdrant
    - Uses query_points for better control
    - Filters by collection_name and optional group_id
    
    Args:
        image: Image file to search
        collection_name: Qdrant collection to search in (default: face_embeddings)
        group_id: Optional filter to search only within a specific group
        confidence: Minimum similarity threshold (0-1)
        limit: Max matches per face to return
    
    Returns:
        List of detected faces with their search results
    """
    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail='No image provided')

    img = read_imagefile(contents)
    if img is None:
        raise HTTPException(status_code=400, detail='Invalid image file')

    try:
        face_objs = extract_faces_from_image(img, detector_backend='retinaface')
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not face_objs:
        return {"faces_detected": 0, "search_results": []}

    # Search for ALL detected faces
    search_results = []
    
    for face_idx, face_obj in enumerate(face_objs):
        area = face_obj['facial_area']
        x, y, w, h = area['x'], area['y'], area['w'], area['h']
        face_img = img[y:y+h, x:x+w]
        face_confidence = float(face_obj.get('confidence', 1.0))

        try:
            query_embedding = get_embedding_from_face(face_img)
        except Exception as e:
            # Skip this face if embedding fails
            print(f"Warning: Could not generate embedding for face {face_idx}: {e}")
            continue

        # Search Qdrant using query_points for better control
        matches = []
        try:
            # Build filter for group_id if provided
            query_filter = None
            if group_id:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="payload.group_id",
                            match=MatchValue(value=group_id)
                        )
                    ]
                )
            
            # Try using query_points (if available in this version of qdrant-client)
            try:
                results = qclient.query_points(
                    collection_name=collection_name, 
                    query=query_embedding,
                    query_filter=query_filter,
                    limit=limit
                ).points
            except AttributeError:
                # Fallback to search method
                results = qclient.search(
                    collection_name=collection_name, 
                    query_vector=query_embedding,
                    query_filter=query_filter, 
                    limit=limit
                )
            
            # Process results
            for rank, hit in enumerate(results, 1):
                similarity_score = hit.score
                
                # Filter by confidence threshold
                if similarity_score >= confidence:
                    match = {
                        'rank': rank,
                        'similarity_score': float(similarity_score),
                        'image_path': hit.payload.get('image_path'),
                        'face_id': hit.payload.get('face_id'),
                        'person_id': hit.payload.get('person_id', 'N/A'),
                        'detection_confidence': hit.payload.get('confidence', 1.0),
                        'facial_area': hit.payload.get('facial_area', {})
                    }
                    matches.append(match)
        
        except Exception as e:
            # Log but don't fail - Qdrant might be empty or unavailable
            print(f"Warning: Qdrant search failed for face {face_idx}: {e}")
            import traceback
            traceback.print_exc()

        # Add this face's search results
        search_results.append({
            'face_id': face_idx,
            'facial_area': {
                'x': int(area['x']),
                'y': int(area['y']),
                'w': int(area['w']),
                'h': int(area['h'])
            },
            'detection_confidence': face_confidence,
            'matches': matches,
            'matches_found': len(matches)
        })

    return {
        "faces_detected": len(face_objs),
        "search_results": search_results
    }


# Background worker functions (digest & cluster)

def digest_worker(job_id: str, local_dir_path: Optional[str], s3_bucket: Optional[str],
                  s3_prefix: Optional[str], gcs_bucket: Optional[str], gcs_prefix: Optional[str],
                  gcs_service_account: Optional[str], group_id: str, collection: str,
                  confidence: float, threads: int, max_retries: int = 2) -> None:
    """
    Process images from local directory, S3 bucket, or GCS bucket, extract faces, generate embeddings,
    create thumbnails, and upsert to Qdrant with multi-threading support, automatic collection creation,
    and comprehensive error tracking.

    For GCS: Creates thumbnails (1000x1000 max) and uploads to /thumbnail/ directory in the same bucket.
    """
    try:
        # Ensure collection exists - auto-create if missing
        try:
            qclient.get_collection(collection)
        except Exception:
            print(f"Collection '{collection}' not found. Creating...")
            try:
                qclient.create_collection(
                    collection_name=collection,
                    vectors_config=VectorParams(size=EMBEDDING_SIZE, distance=Distance.COSINE)
                )
                print(f"Collection '{collection}' created successfully")
            except Exception as e:
                print(f"Warning: Could not create collection '{collection}': {e}")
        
        # Determine source for tracking
        if gcs_bucket:
            source = f"gs://{gcs_bucket}/{gcs_prefix or ''}"
        elif s3_bucket:
            source = f"s3://{s3_bucket}/{s3_prefix or ''}"
        else:
            source = local_dir_path

        # Initialize job tracking with detailed error categories and thumbnail tracking
        ACTIVE_DIGESTS[job_id] = {
            'job_id': job_id,
            'group_id': group_id,
            'status': 'processing',
            'progress': 0,
            'faces_processed': 0,
            'total_images': 0,
            'total_thumbnails_created': 0,
            'total_thumbnails_uploaded': 0,
            'matched_faces': 0,
            'collection': collection,
            'source': source,
            'confidence': confidence,
            'threads': threads,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'error_message': None,
            'upserted_ids': [],
            'successful_images': [],  # Images with faces successfully processed
            'failed_images': [],       # Images that failed processing
            'no_faces_images': [],     # Images with no faces detected
            'thumbnail_failures': [],  # Thumbnail creation/upload failures
            'retry_count': 0
        }
        
        # Collect image files
        image_files = []
        gcs_client = None
        gcs_bucket_obj = None

        if gcs_bucket:
            # Initialize GCS client and list images
            try:
                gcs_client = init_gcs_client(gcs_service_account or 'sa.json')
                gcs_bucket_obj = gcs_client.bucket(gcs_bucket)
                image_files = list_gcs_images(gcs_bucket, gcs_prefix or '', gcs_client)
                print(f"Found {len(image_files)} images in GCS bucket gs://{gcs_bucket}/{gcs_prefix or ''}")
            except Exception as e:
                raise ValueError(f"Failed to list images from GCS: {e}")
        elif local_dir_path:
            dir_path = Path(local_dir_path)
            if not dir_path.exists():
                raise ValueError(f"Directory not found: {local_dir_path}")
            # Collect all image files (jpg, png, jpeg, etc)
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']:
                image_files.extend(dir_path.glob(f"**/{ext}"))
        # TODO: Implement S3 listing with boto3
        
        ACTIVE_DIGESTS[job_id]['total_images'] = len(image_files)
        
        if len(image_files) == 0:
            ACTIVE_DIGESTS[job_id]['status'] = 'completed'
            ACTIVE_DIGESTS[job_id]['progress'] = 100
            ACTIVE_DIGESTS[job_id]['end_time'] = datetime.now().isoformat()
            return
        
        # Process images with ThreadPoolExecutor
        def process_image_file(image_source, retry_count: int = 0) -> Dict[str, Any]:
            """Extract faces from image, create thumbnail, generate embeddings, and return metadata with retry logic."""
            thumbnail_path = None
            thumbnail_created = False
            image_path_str = None

            try:
                # Determine if this is a GCS blob or local path
                is_gcs = isinstance(image_source, storage.Blob)

                if is_gcs:
                    # Download from GCS
                    try:
                        img = download_gcs_image(image_source)
                        image_path_str = f"gs://{image_source.bucket.name}/{image_source.name}"
                    except Exception as e:
                        return {
                            'status': 'failed',
                            'image_path': f"gs://{image_source.bucket.name}/{image_source.name}",
                            'error': f"Failed to download from GCS: {e}",
                            'upserted': 0,
                            'retry_count': retry_count,
                            'thumbnail_created': False,
                            'failure_stage': 'download'
                        }
                else:
                    # Local file
                    img = cv2.imread(str(image_source))
                    image_path_str = str(image_source)

                if img is None:
                    error_msg = "Could not read image file"
                    return {
                        'status': 'failed',
                        'image_path': image_path_str,
                        'error': error_msg,
                        'upserted': 0,
                        'retry_count': retry_count,
                        'thumbnail_created': False,
                        'failure_stage': 'read'
                    }

                # Create and upload thumbnail (for all images, even those with no faces)
                if is_gcs and gcs_bucket_obj:
                    try:
                        thumbnail_bytes = create_thumbnail_from_image(img, max_size=(1000, 1000))
                        thumbnail_path = upload_thumbnail_to_gcs(
                            thumbnail_bytes,
                            image_source.name,
                            gcs_bucket_obj
                        )
                        thumbnail_created = True
                        ACTIVE_DIGESTS[job_id]['total_thumbnails_created'] += 1
                        ACTIVE_DIGESTS[job_id]['total_thumbnails_uploaded'] += 1
                    except Exception as e:
                        print(f"Warning: Thumbnail creation/upload failed for {image_path_str}: {e}")
                        ACTIVE_DIGESTS[job_id]['thumbnail_failures'].append({
                            'path': image_path_str,
                            'error': str(e)
                        })
                        # Continue processing even if thumbnail fails
                
                # Extract faces with retry
                faces = None
                last_error = None
                for attempt in range(max_retries + 1):
                    try:
                        faces = DeepFace.extract_faces(img, detector_backend='retinaface', enforce_detection=False)
                        break
                    except Exception as e:
                        last_error = str(e)
                        if attempt < max_retries:
                            print(f"Retry {attempt + 1}/{max_retries} for {image_path_str}: {e}")
                            continue

                if faces is None:
                    return {
                        'status': 'failed',
                        'image_path': image_path_str,
                        'error': f"Face extraction failed after {max_retries + 1} retries: {last_error}",
                        'upserted': 0,
                        'retry_count': max_retries + 1,
                        'thumbnail_created': thumbnail_created,
                        'thumbnail_path': thumbnail_path,
                        'failure_stage': 'face_extraction'
                    }

                if not faces:
                    return {
                        'status': 'no_faces',
                        'image_path': image_path_str,
                        'error': "No faces detected",
                        'upserted': 0,
                        'retry_count': 0,
                        'thumbnail_created': thumbnail_created,
                        'thumbnail_path': thumbnail_path
                    }
                
                upserted_count = 0
                # Generate embeddings for each face
                for face_idx, face in enumerate(faces):
                    try:
                        face_img = face['face']
                        # Resize to standard size for embedding
                        face_resized = cv2.resize(face_img, (224, 224))
                        
                        # Generate embedding with retry
                        embedding_objs = None
                        for attempt in range(max_retries + 1):
                            try:
                                embedding_objs = DeepFace.represent(face_resized, model_name='ArcFace', enforce_detection=False)
                                break
                            except Exception as e:
                                if attempt < max_retries:
                                    print(f"Embedding retry {attempt + 1}/{max_retries} for face {face_idx} in {image_path_str}")
                                    continue
                                last_error = e

                        if not embedding_objs:
                            continue

                        embedding = embedding_objs[0]['embedding']
                        face_id = str(uuid.uuid4())

                        # Prepare point for Qdrant with thumbnail path
                        facial_area = face.get('facial_area', {})
                        payload_data = {
                            'group_id': group_id,
                            'image_path': image_path_str,
                            'face_index': face_idx,
                            'detection_confidence': float(face.get('confidence', 0.0)),
                            'facial_area': {
                                'x': int(facial_area.get('x', 0)),
                                'y': int(facial_area.get('y', 0)),
                                'w': int(facial_area.get('w', 0)),
                                'h': int(facial_area.get('h', 0))
                            },
                            'timestamp': datetime.now().isoformat()
                        }

                        # Add thumbnail_path if available
                        if thumbnail_path:
                            payload_data['thumbnail_path'] = thumbnail_path

                        point = PointStruct(
                            id=face_id,
                            vector=embedding,
                            payload=payload_data
                        )
                        
                        # Upsert to Qdrant with retry
                        if qclient:
                            for attempt in range(max_retries + 1):
                                try:
                                    qclient.upsert(collection_name=collection, points=[point])
                                    upserted_count += 1
                                    ACTIVE_DIGESTS[job_id]['upserted_ids'].append(face_id)
                                    break
                                except Exception as e:
                                    if attempt < max_retries:
                                        print(f"Qdrant upsert retry {attempt + 1}/{max_retries}: {e}")
                                        continue
                                    raise
                    except Exception as e:
                        print(f"Error processing face {face_idx} from {image_path_str}: {str(e)}")
                        continue

                if upserted_count > 0:
                    return {
                        'status': 'success',
                        'image_path': image_path_str,
                        'upserted': upserted_count,
                        'retry_count': 0,
                        'thumbnail_created': thumbnail_created,
                        'thumbnail_path': thumbnail_path
                    }
                else:
                    return {
                        'status': 'no_faces',
                        'image_path': image_path_str,
                        'error': "No faces successfully processed",
                        'upserted': 0,
                        'retry_count': 0,
                        'thumbnail_created': thumbnail_created,
                        'thumbnail_path': thumbnail_path
                    }
            except Exception as e:
                return {
                    'status': 'failed',
                    'image_path': image_path_str or 'unknown',
                    'error': str(e),
                    'upserted': 0,
                    'retry_count': 0,
                    'thumbnail_created': thumbnail_created,
                    'thumbnail_path': thumbnail_path,
                    'failure_stage': 'general'
                }
        
        # Execute with thread pool
        processed = 0
        with ThreadPoolExecutor(max_workers=threads) as executor:
            for result in executor.map(process_image_file, image_files):
                processed += 1
                
                # Categorize results with thumbnail information
                if result['status'] == 'success':
                    success_entry = {
                        'path': result['image_path'],
                        'faces_extracted': result['upserted'],
                        'thumbnail_created': result.get('thumbnail_created', False)
                    }
                    if result.get('thumbnail_path'):
                        success_entry['thumbnail_path'] = result['thumbnail_path']
                    ACTIVE_DIGESTS[job_id]['successful_images'].append(success_entry)
                    ACTIVE_DIGESTS[job_id]['faces_processed'] += result.get('upserted', 0)
                elif result['status'] == 'no_faces':
                    no_faces_entry = {
                        'path': result['image_path'],
                        'reason': result.get('error', 'No faces detected'),
                        'thumbnail_created': result.get('thumbnail_created', False)
                    }
                    if result.get('thumbnail_path'):
                        no_faces_entry['thumbnail_path'] = result['thumbnail_path']
                    ACTIVE_DIGESTS[job_id]['no_faces_images'].append(no_faces_entry)
                else:  # failed
                    failed_entry = {
                        'path': result['image_path'],
                        'error': result.get('error', 'Unknown error'),
                        'retries': result.get('retry_count', 0),
                        'thumbnail_created': result.get('thumbnail_created', False)
                    }
                    if result.get('failure_stage'):
                        failed_entry['failure_stage'] = result['failure_stage']
                    if result.get('thumbnail_path'):
                        failed_entry['thumbnail_path'] = result['thumbnail_path']
                    ACTIVE_DIGESTS[job_id]['failed_images'].append(failed_entry)
                
                ACTIVE_DIGESTS[job_id]['retry_count'] += result.get('retry_count', 0)
                ACTIVE_DIGESTS[job_id]['progress'] = int((processed / len(image_files)) * 100)
        
        # Mark as completed
        ACTIVE_DIGESTS[job_id]['status'] = 'completed'
        ACTIVE_DIGESTS[job_id]['progress'] = 100
        ACTIVE_DIGESTS[job_id]['end_time'] = datetime.now().isoformat()
        
    except Exception as e:
        ACTIVE_DIGESTS[job_id]['status'] = 'failed'
        ACTIVE_DIGESTS[job_id]['error_message'] = str(e)
        ACTIVE_DIGESTS[job_id]['end_time'] = datetime.now().isoformat()


def cluster_worker(group_id: str, collection: str = QDRANT_COLLECTION, confidence: float = 0.8) -> Dict[str, Any]:
    """
    Cluster faces by group_id using DBSCAN.
    
    Args:
        group_id: The group to cluster
        collection: Qdrant collection name
        confidence: Similarity threshold (0-1). Faces with distance >= (1 - confidence) are same cluster.
                   E.g., confidence=0.8 means distance <= 0.2
    
    Returns:
        Status dict with clustering results
    """
    job_id = f"cluster-{uuid.uuid4()}"
    
    # Initialize cluster job tracking
    ACTIVE_CLUSTERS[job_id] = {
        'job_id': job_id,
        'group_id': group_id,
        'collection': collection,
        'confidence': confidence,
        'status': 'processing',
        'message': 'Clustering in progress...',
        'total_faces': 0,
        'clusters_created': 0,
        'faces_updated': 0,
        'start_time': datetime.now().isoformat(),
        'end_time': None,
        'error': None,
        'updated_faces': []
    }
    
    try:
        # Fetch all points with this group_id
        all_points = []
        offset = 0
        batch_size = 100
        
        while True:
            try:
                points = qclient.scroll(
                    collection_name=collection,
                    limit=batch_size,
                    offset=offset,
                    with_vectors=True,
                    with_payload=True
                )[0]
                
                if not points:
                    break
                
                # Filter by group_id
                for point in points:
                    if point.payload.get('group_id') == group_id:
                        all_points.append(point)
                
                offset += batch_size
            except Exception as e:
                print(f"[cluster] Error scrolling: {e}")
                break
        
        if not all_points:
            ACTIVE_CLUSTERS[job_id].update({
                'status': 'completed',
                'message': f'No faces found for group_id: {group_id}',
                'total_faces': 0,
                'clusters_created': 0,
                'end_time': datetime.now().isoformat()
            })
            return ACTIVE_CLUSTERS[job_id]
        
        # Extract embeddings and point IDs
        embeddings = np.array([point.vector for point in all_points])
        point_ids = [point.id for point in all_points]
        
        print(f"[cluster] Clustering {len(all_points)} faces with confidence={confidence}")
        
        # Convert confidence to eps for DBSCAN
        # confidence=0.8 means we want to group faces that are 80% similar
        # distance = 1 - cosine_similarity, so eps = 1 - confidence
        eps = 1 - confidence
        
        # Run DBSCAN clustering
        # eps: maximum distance between two samples for them to be in the same neighborhood
        # min_samples: minimum number of samples in a neighborhood for a point to be considered core point
        distances = cosine_distances(embeddings)
        clusterer = DBSCAN(eps=eps, min_samples=1, metric='precomputed')
        cluster_labels = clusterer.fit_predict(distances)
        
        # Group points by cluster
        clusters = {}
        for idx, label in enumerate(cluster_labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append({
                'point_id': point_ids[idx],
                'index': idx,
                'original_face_id': all_points[idx].payload.get('face_id')
            })
        
        # Assign person_id to each cluster and update Qdrant
        person_id_counter = 1
        updated_count = 0
        updated_faces = []
        
        for cluster_id, faces in clusters.items():
            person_id = f"person_{group_id}_{person_id_counter}"
            
            # Update all faces in this cluster with the same person_id
            for face in faces:
                try:
                    qclient.set_payload(
                        collection_name=collection,
                        payload_key="person_id",
                        payload=person_id,
                        points=[face['point_id']]
                    )
                    updated_count += 1
                    updated_faces.append({
                        'point_id': face['point_id'],
                        'original_face_id': face['original_face_id'],
                        'person_id': person_id,
                        'cluster_id': cluster_id,
                        'cluster_size': len(faces)
                    })
                except Exception as e:
                    print(f"[cluster] Error updating point {face['point_id']}: {e}")
            
            person_id_counter += 1
        
        result = {
            "job_id": job_id,
            "status": "completed",
            "message": f"Successfully clustered {len(all_points)} faces into {len(clusters)} clusters",
            "group_id": group_id,
            "collection": collection,
            "confidence": confidence,
            "total_faces": len(all_points),
            "clusters_created": len(clusters),
            "faces_updated": updated_count,
            "updated_faces": updated_faces[:50]  # Return first 50 for preview
        }
        
        ACTIVE_CLUSTERS[job_id].update({
            'status': 'completed',
            'message': result['message'],
            'total_faces': len(all_points),
            'clusters_created': len(clusters),
            'faces_updated': updated_count,
            'updated_faces': updated_faces[:50],
            'end_time': datetime.now().isoformat()
        })
        
        print(f"[cluster] Completed: {result['message']}")
        return ACTIVE_CLUSTERS[job_id]
        
    except Exception as e:
        print(f"[cluster] Error: {e}")
        ACTIVE_CLUSTERS[job_id].update({
            'status': 'failed',
            'error': str(e),
            'message': f'Clustering failed: {str(e)}',
            'end_time': datetime.now().isoformat()
        })
        return ACTIVE_CLUSTERS[job_id]


# If Celery is configured, register tasks
if celery_app:
    @celery_app.task(name='tasks.digest_task')
    def celery_digest_task(s3_bucket, s3_prefix, group_id):
        return digest_worker(s3_bucket, s3_prefix, group_id)

    @celery_app.task(name='tasks.cluster_task')
    def celery_cluster_task(group_id, collection, confidence):
        return cluster_worker(group_id, collection, confidence)


class DigestRequest(BaseModel):
    s3_bucket: Optional[str] = None
    s3_prefix: Optional[str] = None
    gcs_bucket: Optional[str] = None
    gcs_prefix: Optional[str] = None
    gcs_service_account: Optional[str] = 'sa.json'
    local_dir_path: Optional[str] = None
    group_id: str
    collection: str = QDRANT_COLLECTION
    confidence: float = 0.5
    threads: int = 4
    max_retries: int = 2

    class Config:
        json_schema_extra = {
            "example": {
                "gcs_bucket": "my-bucket",
                "gcs_prefix": "photos/",
                "group_id": "engagement_photos",
                "collection": "face_embeddings",
                "confidence": 0.7,
                "threads": 4,
                "max_retries": 2
            }
        }
    
    def __init__(self, **data):
        super().__init__(**data)
        # Validate that either gcs_bucket, s3_bucket+s3_prefix, or local_dir_path is provided
        has_gcs = bool(self.gcs_bucket)
        has_s3 = bool(self.s3_bucket and self.s3_prefix)
        has_local = bool(self.local_dir_path)

        sources_count = sum([has_gcs, has_s3, has_local])

        if sources_count == 0:
            raise ValueError("Either gcs_bucket, s3_bucket+s3_prefix, or local_dir_path must be provided")
        if sources_count > 1:
            raise ValueError("Cannot specify multiple sources (GCS, S3, or local directory). Choose only one.")


@app.post('/digest')
async def digest_endpoint(req: DigestRequest, background_tasks: BackgroundTasks):
    """
    Start a digest process to extract faces from images, create thumbnails, and add to Qdrant.

    Accepts either gcs_bucket, s3_bucket+s3_prefix, or local_dir_path (not multiple).
    Returns immediately with a job_id for async tracking.

    For GCS: Creates thumbnails (1000x1000 max) and uploads to /thumbnail/ directory.

    Example:
      POST /digest with {
        "gcs_bucket": "my-bucket",
        "gcs_prefix": "photos/",
        "group_id": "event_name",
        "confidence": 0.7,
        "threads": 4
      }
    """
    job_id = f"digest-{uuid.uuid4()}"

    # Schedule background task with GCS support
    background_tasks.add_task(
        digest_worker,
        job_id=job_id,
        local_dir_path=req.local_dir_path,
        s3_bucket=req.s3_bucket,
        s3_prefix=req.s3_prefix,
        gcs_bucket=req.gcs_bucket,
        gcs_prefix=req.gcs_prefix,
        gcs_service_account=req.gcs_service_account,
        group_id=req.group_id,
        collection=req.collection,
        confidence=req.confidence,
        threads=req.threads,
        max_retries=req.max_retries
    )

    return JSONResponse(status_code=202, content={
        "job_id": job_id,
        "status": "queued",
        "message": "Digest task queued for processing"
    })


@app.get('/get-digests')
async def get_digests_endpoint():
    """
    Get status of all active and recent digestion processes.
    
    Returns list of digest jobs with their status, progress, and metadata.
    """
    return {
        "total_jobs": len(ACTIVE_DIGESTS),
        "jobs": list(ACTIVE_DIGESTS.values())
    }


@app.get('/get-digests/{job_id}')
async def get_digest_status(job_id: str):
    """
    Get detailed status of a specific digestion process.
    
    Returns job information or 404 if not found.
    """
    if job_id not in ACTIVE_DIGESTS:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return ACTIVE_DIGESTS[job_id]


@app.get('/get-clusters')
async def get_clusters_endpoint():
    """
    Get status of all active and recent clustering processes.
    
    Returns list of cluster jobs with their status, progress, and metadata.
    """
    return {
        "total_jobs": len(ACTIVE_CLUSTERS),
        "jobs": list(ACTIVE_CLUSTERS.values())
    }


@app.get('/get-clusters/{job_id}')
async def get_cluster_status(job_id: str):
    """
    Get detailed status of a specific clustering process.
    
    Returns job information or 404 if not found.
    """
    if job_id not in ACTIVE_CLUSTERS:
        raise HTTPException(status_code=404, detail=f"Cluster job {job_id} not found")
    
    return ACTIVE_CLUSTERS[job_id]


class ClusterRequest(BaseModel):
    group_id: str
    collection: str = QDRANT_COLLECTION
    confidence: float = 0.8  # Similarity threshold for clustering (0-1)


@app.post('/cluster-faces')
async def cluster_endpoint(req: ClusterRequest, background_tasks: BackgroundTasks):
    if celery_app:
        res = celery_cluster_task.delay(req.group_id, req.collection, req.confidence)
        return JSONResponse(status_code=202, content={"job_id": res.id, "status": "started", "message": "Clustering task queued"})
    else:
        job_id = f"cluster-{uuid.uuid4()}"
        background_tasks.add_task(cluster_worker, req.group_id, req.collection, req.confidence)
        return JSONResponse(status_code=202, content={"job_id": job_id, "status": "started", "message": "Clustering task started in background (no Celery)"})


# Root
@app.get('/')
async def root():
    return {"service": "Face Worker Service", "status": "ok", "qdrant_collection": QDRANT_COLLECTION}
