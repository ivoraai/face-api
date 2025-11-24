import cv2
import numpy as np
from pathlib import Path
import os
from deepface import DeepFace
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from dotenv import load_dotenv
import uuid
import json
from datetime import datetime
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import time
from threading import RLock
import signal
from contextlib import contextmanager

# Load environment variables
load_dotenv()

# Global lock for DeepFace operations (DeepFace is not thread-safe)
deepface_lock = RLock()

class FaceEmbeddingProcessor:
    """Process images from directory and store face embeddings in Qdrant"""

    def __init__(self, collection_name="face_embeddings", image_directory=None):
        """
        Initialize the processor with Qdrant connection

        Args:
            collection_name: Name of the Qdrant collection to use
            image_directory: Absolute path to directory containing images (optional)
        """
        # Store directory path
        self.image_directory = Path(image_directory).absolute() if image_directory else None

        # Get Qdrant credentials from environment
        self.qdrant_url = os.getenv("QDRANT_URL", "localhost")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY", None)

        # Initialize Qdrant client
        if self.qdrant_api_key:
            self.client = QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key
            )
        else:
            self.client = QdrantClient(
                host=self.qdrant_url,
                port=self.qdrant_port
            )

        self.collection_name = collection_name
        self.embedding_size = 512  # Facenet512 embedding size

        # Tracking files
        self.progress_file = "processing_progress.json"
        self.no_faces_log_file = "no_faces_detected.json"

        # Thumbnail settings
        self.thumbnail_size = (512, 512)
        self.thumbnail_quality = 85

        # Thread safety (using RLock for reentrancy)
        self.progress_lock = RLock()
        self.stats_lock = RLock()

        # Retry settings
        self.max_retries = 3
        self.retry_delay = 2  # seconds

        # Create collection if it doesn't exist
        self._setup_collection()

    def _setup_collection(self):
        """Create Qdrant collection if it doesn't exist"""
        try:
            self.client.get_collection(self.collection_name)
            print(f"Collection '{self.collection_name}' already exists")
        except:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.embedding_size, distance=Distance.COSINE)
            )
            print(f"Created collection '{self.collection_name}'")

    def reset_collection(self):
        """Delete and recreate the collection"""
        try:
            self.client.delete_collection(self.collection_name)
            print(f"Deleted collection '{self.collection_name}'")
        except:
            print(f"Collection '{self.collection_name}' doesn't exist")

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.embedding_size, distance=Distance.COSINE)
        )
        print(f"Created fresh collection '{self.collection_name}'")

    def load_progress(self):
        """Load the list of already processed images"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('processed_images', []))
            except Exception as e:
                print(f"  Warning: Could not load progress file: {e}")
                return set()
        return set()

    def save_progress(self, processed_images):
        """Save the list of processed images (thread-safe)"""
        with self.progress_lock:
            try:
                data = {
                    'processed_images': list(processed_images),
                    'last_updated': datetime.now().isoformat()
                }
                with open(self.progress_file, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                print(f"  Warning: Could not save progress: {e}")

    def upsert_to_qdrant_with_retry(self, points):
        """
        Upsert points to Qdrant with retry mechanism

        Args:
            points: List of PointStruct objects to upsert

        Returns:
            bool: True if successful, False otherwise
        """
        for attempt in range(self.max_retries):
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                return True
            except Exception as e:
                if attempt < self.max_retries - 1:
                    print(f"  Qdrant upsert failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                    print(f"  Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    print(f"  Qdrant upsert failed after {self.max_retries} attempts: {e}")
                    return False
        return False

    def log_no_faces_image(self, image_path, error_message):
        """Log images where no faces were detected"""
        try:
            # Load existing log
            no_faces_list = []
            if os.path.exists(self.no_faces_log_file):
                with open(self.no_faces_log_file, 'r') as f:
                    no_faces_list = json.load(f)

            # Add new entry
            entry = {
                'image_path': str(image_path),
                'timestamp': datetime.now().isoformat(),
                'error': error_message
            }
            no_faces_list.append(entry)

            # Save updated log
            with open(self.no_faces_log_file, 'w') as f:
                json.dump(no_faces_list, f, indent=2)

        except Exception as e:
            print(f"  Warning: Could not log no-faces image: {e}")

    def encode_thumbnail(self, face_img):
        """
        Encode face image as base64 string

        Args:
            face_img: Face image (numpy array)

        Returns:
            Base64 encoded string of the thumbnail
        """
        try:
            # Resize to thumbnail size
            thumbnail = cv2.resize(face_img, self.thumbnail_size)

            # Encode as JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.thumbnail_quality]
            _, buffer = cv2.imencode('.jpg', thumbnail, encode_param)

            # Convert to base64
            thumbnail_base64 = base64.b64encode(buffer).decode('utf-8')

            return thumbnail_base64

        except Exception as e:
            print(f"  Warning: Could not encode thumbnail: {e}")
            return None

    def get_all_images(self, directory, extensions=None, exclude_dirs=None):
        """
        Recursively get all image files from directory

        Args:
            directory: Root directory to search
            extensions: List of image extensions to search for
            exclude_dirs: List of directory names to exclude (e.g., ['.venv', 'node_modules'])

        Returns:
            List of Path objects for all images found
        """
        if extensions is None:
            extensions = ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG', '.bmp', '.BMP']

        if exclude_dirs is None:
            exclude_dirs = ['.venv', 'venv', 'node_modules', '__pycache__', '.git']

        image_files = []
        directory_path = Path(directory)

        for ext in extensions:
            # Use glob with ** for recursive search
            for img_path in directory_path.rglob(f'*{ext}'):
                # Check if any parent directory is in exclude list
                if not any(excluded in img_path.parts for excluded in exclude_dirs):
                    image_files.append(img_path)

        return sorted(image_files)

    def extract_face_embeddings(self, image_path):
        """
        Extract face embeddings from a single image

        Args:
            image_path: Path to the image file

        Returns:
            Tuple: (results list, error_message)
            - results: List of dictionaries with face data and embeddings
            - error_message: Error message if no faces found, None otherwise
        """
        results = []
        error_message = None

        try:
            # Read the image
            img = cv2.imread(str(image_path))
            if img is None:
                error_message = f"Could not read image {image_path}"
                print(f"  Warning: {error_message}")
                return results, error_message

            # Use lock for DeepFace operations (not thread-safe)
            with deepface_lock:
                # Detect faces using DeepFace with RetinaFace (96.2% accuracy)
                face_objs = DeepFace.extract_faces(
                    img_path=str(image_path),
                    detector_backend='retinaface',
                    enforce_detection=True,
                    align=True
                )

                if not face_objs:
                    error_message = f"No faces found in {image_path}"
                    print(f"  {error_message}")
                    return results, error_message

                # Process each face
                for idx, face_obj in enumerate(face_objs):
                    facial_area = face_obj['facial_area']
                    confidence = face_obj['confidence']

                    # Extract raw face region from original image (before any normalization)
                    x, y, w, h = facial_area['x'], facial_area['y'], facial_area['w'], facial_area['h']
                    face_img = img[y:y+h, x:x+w]

                    # Generate thumbnail
                    thumbnail_base64 = self.encode_thumbnail(face_img)

                    # Generate embedding using ArcFace (99.82% LFW accuracy, 98.37% CFP-FP)
                    try:
                        embedding = DeepFace.represent(
                            img_path=face_img,
                            model_name='ArcFace',
                            enforce_detection=False,
                            detector_backend='skip'
                        )

                        embedding_vector = np.array(embedding[0]['embedding'])

                        result = {
                            'face_id': idx,
                            'image_path': str(image_path.absolute()),
                            'facial_area': facial_area,
                            'confidence': confidence,
                            'embedding': embedding_vector,
                            'thumbnail': thumbnail_base64
                        }

                        results.append(result)

                    except Exception as e:
                        print(f"  Error generating embedding for face {idx} in {image_path}: {e}")
                        continue

        except Exception as e:
            error_message = str(e)
            print(f"  Error processing {image_path}: {e}")

        return results, error_message

    def process_single_image(self, img_path, processed_images):
        """
        Process a single image and store embeddings in Qdrant

        Args:
            img_path: Path object for the image
            processed_images: Set of already processed images

        Returns:
            Dictionary with processing result
        """
        result = {
            'image_path': str(img_path),
            'success': False,
            'faces_count': 0,
            'error': None,
            'skipped': False
        }

        img_path_str = str(img_path.absolute())

        # Check if already processed
        with self.progress_lock:
            if img_path_str in processed_images:
                result['skipped'] = True
                print(f"\n[SKIP] {img_path.name}")
                return result

        print(f"\n[START] Processing: {img_path.name}")

        try:
            # Get image creation timestamp
            image_created_time = None
            try:
                stat_info = os.stat(img_path)
                creation_time = getattr(stat_info, 'st_birthtime', stat_info.st_mtime)
                image_created_time = datetime.fromtimestamp(creation_time).isoformat()
            except Exception as e:
                print(f"  [WARN] Could not get image creation time: {e}")

            # Extract embeddings
            print(f"  [DETECT] Detecting faces in {img_path.name}...")
            try:
                face_data, error_message = self.extract_face_embeddings(img_path)
                print(f"  [DETECT] Found {len(face_data) if face_data else 0} faces")
            except Exception as e:
                print(f"  [ERROR] Face detection failed: {e}")
                raise

            if face_data:
                # Prepare points for Qdrant
                points_for_this_image = []
                for face in face_data:
                    point_id = str(uuid.uuid4())

                    payload = {
                        'image_path': face['image_path'],
                        'face_id': face['face_id'],
                        'facial_area': face['facial_area'],
                        'confidence': float(face['confidence'])
                    }

                    # Add thumbnail if available
                    if face.get('thumbnail'):
                        payload['face_thumbnail'] = face['thumbnail']

                    # Add image creation time if available
                    if image_created_time:
                        payload['image_created_time'] = image_created_time

                    point = PointStruct(
                        id=point_id,
                        vector=face['embedding'].tolist(),
                        payload=payload
                    )

                    points_for_this_image.append(point)

                # Insert points for this image into Qdrant with retry
                print(f"  [QDRANT] Upserting {len(face_data)} faces to Qdrant...", flush=True)
                if self.upsert_to_qdrant_with_retry(points_for_this_image):
                    print(f"  [SUCCESS] {len(face_data)} face(s) - Updated Qdrant", flush=True)
                    result['success'] = True
                    result['faces_count'] = len(face_data)

                    # Mark as processed
                    with self.progress_lock:
                        processed_images.add(img_path_str)
                        self.save_progress(processed_images)
                    print(f"  [SAVE] Progress saved", flush=True)
                else:
                    result['error'] = "Failed to upsert to Qdrant after retries"
                    print(f"  [ERROR] {result['error']}", flush=True)

            else:
                # No faces detected
                result['error'] = error_message or "No faces detected"

                # Log to no_faces file
                if error_message:
                    self.log_no_faces_image(img_path, error_message)

                # Still mark as processed to avoid reprocessing
                with self.progress_lock:
                    processed_images.add(img_path_str)
                    self.save_progress(processed_images)

        except Exception as e:
            result['error'] = f"Unexpected error: {str(e)}"
            print(f"  Unexpected error processing {img_path}: {e}")
            self.log_no_faces_image(img_path, result['error'])

        return result

    def process_directory(self, directory=None, num_workers=1):
        """
        Process all images in directory and store embeddings in Qdrant
        Updates Qdrant incrementally after each image for fault tolerance
        Supports parallel processing with multiple workers

        Args:
            directory: Directory containing images (optional, uses instance directory if not provided)
            num_workers: Number of parallel workers (default: 1 for sequential processing)

        Returns:
            Dictionary with processing statistics
        """
        # Use provided directory or fall back to instance directory
        if directory is None:
            if self.image_directory is None:
                raise ValueError("No directory specified. Provide directory parameter or set during initialization.")
            directory = self.image_directory

        print(f"Searching for images in: {directory}")
        image_files = self.get_all_images(directory)

        print(f"Found {len(image_files)} image files")
        print(f"Processing with {num_workers} worker(s)")

        # Load progress to support resume
        processed_images = self.load_progress()
        print(f"Already processed: {len(processed_images)} images")

        stats = {
            'total_images': len(image_files),
            'processed_images': 0,
            'total_faces': 0,
            'failed_images': 0,
            'no_faces_images': 0,
            'skipped_images': 0
        }

        if num_workers == 1:
            # Sequential processing
            for img_path in image_files:
                result = self.process_single_image(img_path, processed_images)

                # Update stats
                if result['skipped']:
                    stats['skipped_images'] += 1
                elif result['success']:
                    stats['processed_images'] += 1
                    stats['total_faces'] += result['faces_count']
                elif result['error']:
                    if 'No faces' in result['error']:
                        stats['no_faces_images'] += 1
                    else:
                        stats['failed_images'] += 1
        else:
            # Parallel processing with ThreadPoolExecutor
            print(f"\nStarting parallel processing with {num_workers} workers...")

            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                # Submit all tasks
                future_to_img = {
                    executor.submit(self.process_single_image, img_path, processed_images): img_path
                    for img_path in image_files
                }

                # Process completed tasks
                completed = 0
                for future in as_completed(future_to_img, timeout=None):
                    completed += 1
                    img_path = future_to_img[future]

                    try:
                        # Get result with timeout (5 minutes per image max)
                        result = future.result(timeout=300)

                        # Update stats (thread-safe)
                        with self.stats_lock:
                            if result['skipped']:
                                stats['skipped_images'] += 1
                            elif result['success']:
                                stats['processed_images'] += 1
                                stats['total_faces'] += result['faces_count']
                            elif result['error']:
                                if 'No faces' in result['error']:
                                    stats['no_faces_images'] += 1
                                else:
                                    stats['failed_images'] += 1

                        # Progress indicator
                        print(f"\n[PROGRESS] {completed}/{len(image_files)} images processed", flush=True)

                    except TimeoutError:
                        print(f"\n[TIMEOUT] Processing {img_path.name} timed out after 5 minutes", flush=True)
                        with self.stats_lock:
                            stats['failed_images'] += 1
                    except Exception as e:
                        print(f"\n[ERROR] Worker error processing {img_path.name}: {e}", flush=True)
                        with self.stats_lock:
                            stats['failed_images'] += 1

        return stats

    def assign_person_ids_incremental(self, points_to_assign, similarity_threshold=0.80):
        """
        Assign person_id to new faces using incremental clustering

        Args:
            points_to_assign: list of PointStruct objects (newly added faces)
            similarity_threshold: cosine similarity threshold for same person

        Returns:
            Number of faces assigned person_ids
        """
        print(f"\nAssigning person_ids to {len(points_to_assign)} new faces...")

        assigned_count = 0

        for point in points_to_assign:
            # Search for similar faces
            search_results = self.client.query_points(
                collection_name=self.collection_name,
                query=point.vector,
                limit=10,
                query_filter=None  # Search all faces
            ).points

            # Find best match above threshold
            best_match_person_id = None
            best_similarity = 0.0

            for hit in search_results:
                # Skip self
                if hit.id == point.id:
                    continue

                # Check if has person_id and similarity
                if 'person_id' in hit.payload and hit.score >= similarity_threshold:
                    if hit.score > best_similarity:
                        best_similarity = hit.score
                        best_match_person_id = hit.payload['person_id']

            # Assign person_id
            if best_match_person_id is not None:
                # Match found - assign existing person_id
                person_id = best_match_person_id
                confidence = "high" if best_similarity > 0.85 else "medium"
            else:
                # No match - create new person_id
                # Find max existing person_id
                try:
                    all_points = self.client.scroll(
                        collection_name=self.collection_name,
                        limit=1,
                        with_payload=True,
                        with_vectors=False
                    )[0]

                    max_person_id = 0
                    if all_points:
                        for p in all_points:
                            if 'person_id' in p.payload:
                                max_person_id = max(max_person_id, p.payload['person_id'])

                    person_id = max_person_id + 1
                except:
                    person_id = 1

                confidence = "new"

            # Update point with person_id
            from datetime import datetime
            self.client.set_payload(
                collection_name=self.collection_name,
                payload={
                    "person_id": int(person_id),
                    "cluster_timestamp": datetime.now().isoformat(),
                    "cluster_confidence": confidence
                },
                points=[point.id]
            )

            assigned_count += 1

        print(f"✓ Assigned person_ids to {assigned_count} faces")
        return assigned_count

    def search_similar_faces(self, query_image_path, limit=5):
        """
        Search for similar faces in the database

        Args:
            query_image_path: Path to query image
            limit: Number of similar faces to return

        Returns:
            List of similar faces with scores
        """
        # Extract embedding from query image
        face_data, error_message = self.extract_face_embeddings(Path(query_image_path))

        if not face_data:
            print(f"No faces found in query image: {error_message if error_message else 'Unknown error'}")
            return []

        # Use the first face for search
        query_embedding = face_data[0]['embedding'].tolist()

        # Search in Qdrant
        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit
        )

        results = []
        for hit in search_results:
            results.append({
                'image_path': hit.payload['image_path'],
                'face_id': hit.payload['face_id'],
                'similarity_score': hit.score,
                'confidence': hit.payload['confidence']
            })

        return results


if __name__ == "__main__":
    import argparse

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Process images and extract face embeddings to Qdrant',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sequential processing (default)
  uv run python face_embedding_processor.py --collection my_faces --dir /path/to/images

  # Parallel processing with 4 workers
  uv run python face_embedding_processor.py -c wedding_photos -d "/Users/name/Photos/Wedding" -w 4

  # Parallel processing with 8 workers (faster for large datasets)
  uv run python face_embedding_processor.py -c event_photos -d /path/to/images --workers 8

  # Short form
  uv run python face_embedding_processor.py -c my_collection -d . -w 4
        """
    )

    parser.add_argument(
        '--collection', '-c',
        type=str,
        default='face_embeddings',
        help='Qdrant collection name (default: face_embeddings)'
    )

    parser.add_argument(
        '--dir', '-d',
        type=str,
        required=True,
        help='Absolute path to directory containing images (required)'
    )

    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=1,
        help='Number of parallel workers for processing (default: 1, use 4-8 for parallel processing)'
    )

    args = parser.parse_args()

    # Initialize processor with command-line arguments
    print(f"Initializing Face Embedding Processor...")
    print(f"Collection: {args.collection}")
    print(f"Directory: {args.dir}")
    print(f"Workers: {args.workers}")

    processor = FaceEmbeddingProcessor(
        collection_name=args.collection,
        image_directory=args.dir
    )

    # Process images
    stats = processor.process_directory(num_workers=args.workers)

    print(f"\n{'='*50}")
    print("Processing Summary:")
    print(f"{'='*50}")
    print(f"Total images found: {stats['total_images']}")
    print(f"Skipped (already processed): {stats['skipped_images']}")
    print(f"Successfully processed: {stats['processed_images']}")
    print(f"No faces detected: {stats['no_faces_images']}")
    print(f"Failed to process: {stats['failed_images']}")
    print(f"Total faces detected: {stats['total_faces']}")
    print(f"{'='*50}")
    print(f"\nProgress saved to: {processor.progress_file}")
    print(f"No-faces log saved to: {processor.no_faces_log_file}")
