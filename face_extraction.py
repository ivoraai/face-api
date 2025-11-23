import cv2
import numpy as np
from pathlib import Path
import tempfile
import os
from deepface import DeepFace

def extract_faces_and_embeddings(image_path, temp_dir=None, thumbnail_size=(128, 128)):
    """
    Extract all faces from an image, extract facial features and convert to embeddings.

    Args:
        image_path: Path to the input image
        temp_dir: Directory to store extracted faces (uses system temp if None)
        thumbnail_size: Tuple (width, height) for thumbnail size, default (128, 128)

    Returns:
        List of dictionaries containing face info, embeddings, and saved paths
    """
    # Create temp directory if not provided
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="faces_")
    else:
        Path(temp_dir).mkdir(parents=True, exist_ok=True)

    print(f"Using temp directory: {temp_dir}")

    # Read the image
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image from {image_path}")

    print(f"Image loaded: {img.shape}")

    # Detect faces using DeepFace (with multiple backends)
    results = []

    try:
        # Extract faces and embeddings using DeepFace
        face_objs = DeepFace.extract_faces(
            img_path=image_path,
            detector_backend='opencv',  # Options: 'opencv', 'mtcnn', 'retinaface', 'ssd'
            enforce_detection=False,
            align=True
        )

        print(f"Found {len(face_objs)} face(s)")

        for idx, face_obj in enumerate(face_objs):
            # Get face region
            facial_area = face_obj['facial_area']
            confidence = face_obj['confidence']

            # Extract face from original image
            x, y, w, h = facial_area['x'], facial_area['y'], facial_area['w'], facial_area['h']
            face_img = img[y:y+h, x:x+w]

            # Save original face image
            face_filename = f"face_{idx+1}.jpg"
            face_path = os.path.join(temp_dir, face_filename)
            cv2.imwrite(face_path, face_img)

            # Create and save thumbnail
            thumbnail_img = cv2.resize(face_img, thumbnail_size, interpolation=cv2.INTER_AREA)
            thumbnail_filename = f"face_{idx+1}_thumbnail.jpg"
            thumbnail_path = os.path.join(temp_dir, thumbnail_filename)
            cv2.imwrite(thumbnail_path, thumbnail_img)

            # Generate embedding using DeepFace
            embedding = DeepFace.represent(
                img_path=face_path,
                model_name='Facenet512',  # Options: 'VGG-Face', 'Facenet', 'Facenet512', 'OpenFace', 'DeepFace', 'DeepID', 'ArcFace', 'Dlib'
                enforce_detection=False
            )

            # Extract the embedding vector
            embedding_vector = np.array(embedding[0]['embedding'])

            result = {
                'face_id': idx + 1,
                'face_path': face_path,
                'thumbnail_path': thumbnail_path,
                'facial_area': facial_area,
                'confidence': confidence,
                'embedding': embedding_vector,
                'embedding_size': len(embedding_vector)
            }

            results.append(result)

            print(f"Face {idx+1}: Saved to {face_path}")
            print(f"  Thumbnail: {thumbnail_path} ({thumbnail_size[0]}x{thumbnail_size[1]})")
            print(f"  Embedding size: {len(embedding_vector)}")

    except Exception as e:
        print(f"Error processing faces: {e}")
        raise

    return results, temp_dir


if __name__ == "__main__":
    # Example usage
    image_path = "img.JPG"  # Replace with your image path

    # Extract faces and embeddings
    try:
        results, temp_dir = extract_faces_and_embeddings(image_path)

        print(f"\n{'='*50}")
        print(f"Summary:")
        print(f"{'='*50}")
        print(f"Total faces detected: {len(results)}")
        print(f"Temp directory: {temp_dir}")

        for result in results:
            print(f"\nFace {result['face_id']}:")
            print(f"  - Path: {result['face_path']}")
            print(f"  - Thumbnail: {result['thumbnail_path']}")
            print(f"  - Location: x={result['facial_area']['x']}, y={result['facial_area']['y']}")
            print(f"  - Size: {result['facial_area']['w']}x{result['facial_area']['h']}")
            print(f"  - Confidence: {result['confidence']:.2f}")
            print(f"  - Embedding shape: {result['embedding'].shape}")
            print(f"  - Embedding (first 5 values): {result['embedding'][:5]}")

    except Exception as e:
        print(f"Error: {e}")
