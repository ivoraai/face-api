import sys
from pathlib import Path
from face_embedding_processor import FaceEmbeddingProcessor


def search_faces_in_image(image_path, top_k=5):
    """
    Search for all faces in an image and find similar faces in Qdrant

    Args:
        image_path: Path to the query image
        top_k: Number of similar faces to return for each detected face

    Returns:
        List of search results for each face found
    """
    print(f"Processing image: {image_path}")
    print(f"{'='*60}")

    # Initialize processor
    processor = FaceEmbeddingProcessor(collection_name="face_embeddings")

    # Extract faces and embeddings from the query image
    face_data, error_message = processor.extract_face_embeddings(Path(image_path))

    if not face_data:
        print(f"No faces found in the image! {error_message if error_message else ''}")
        return []

    print(f"\nFound {len(face_data)} face(s) in the image\n")

    all_results = []

    # Search for each face
    for idx, face in enumerate(face_data):
        print(f"{'─'*60}")
        print(f"Face {idx + 1}:")
        print(f"{'─'*60}")
        print(f"  Location: ({face['facial_area']['x']}, {face['facial_area']['y']})")
        print(f"  Size: {face['facial_area']['w']}x{face['facial_area']['h']}")
        print(f"  Confidence: {face['confidence']:.2f}")

        # Search for similar faces in Qdrant
        search_results = processor.client.query_points(
            collection_name=processor.collection_name,
            query=face['embedding'].tolist(),
            limit=top_k
        ).points

        print(f"\n  Top {top_k} Similar Faces:")
        print(f"  {'-'*56}")

        face_results = []
        for rank, hit in enumerate(search_results, 1):
            person_id = hit.payload.get('person_id', 'N/A')
            result = {
                'rank': rank,
                'image_path': hit.payload['image_path'],
                'face_id': hit.payload['face_id'],
                'person_id': person_id,
                'similarity_score': hit.score,
                'confidence': hit.payload['confidence'],
                'facial_area': hit.payload['facial_area']
            }
            face_results.append(result)

            print(f"  {rank}. Score: {hit.score:.4f}")
            print(f"     Person ID: {person_id}")
            print(f"     Image: {hit.payload['image_path']}")
            print(f"     Face ID: {hit.payload['face_id']}")
            print(f"     Detection Confidence: {hit.payload['confidence']:.2f}")
            print()

        all_results.append({
            'query_face_id': idx,
            'query_face_info': {
                'facial_area': face['facial_area'],
                'confidence': face['confidence']
            },
            'matches': face_results
        })

    return all_results


if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python face_search.py <image_path> [top_k]")
        print("\nExample:")
        print("  python face_search.py query_image.jpg")
        print("  python face_search.py query_image.jpg 10")
        sys.exit(1)

    image_path = sys.argv[1]
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    # Verify image exists
    if not Path(image_path).exists():
        print(f"Error: Image not found at {image_path}")
        sys.exit(1)

    # Search for faces
    results = search_faces_in_image(image_path, top_k)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total faces detected in query image: {len(results)}")
    print(f"Top {top_k} matches retrieved for each face")
    print(f"{'='*60}")
