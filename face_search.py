import sys
import argparse
from pathlib import Path
from face_embedding_processor import FaceEmbeddingProcessor


def search_faces_in_image(image_path, collection_name="face_embeddings", top_k=5, threshold=0.0):
    """
    Search for all faces in an image and find similar faces in Qdrant

    Args:
        image_path: Path to the query image
        collection_name: Name of the Qdrant collection to search
        top_k: Number of similar faces to return for each detected face
        threshold: Minimum similarity threshold (0.0 to 1.0, where 1.0 is identical)

    Returns:
        List of search results for each face found
    """
    print(f"Processing image: {image_path}")
    print(f"Collection: {collection_name}")
    print(f"Similarity threshold: {threshold*100:.1f}%")
    print(f"{'='*60}")

    # Initialize processor
    processor = FaceEmbeddingProcessor(collection_name=collection_name)

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

        # Filter results by threshold
        filtered_results = [hit for hit in search_results if hit.score >= threshold]

        if not filtered_results:
            print(f"\n  No matches found above {threshold*100:.1f}% threshold")
        else:
            print(f"\n  Top {len(filtered_results)} Similar Faces (above {threshold*100:.1f}% threshold):")
            print(f"  {'-'*56}")

        face_results = []
        for rank, hit in enumerate(filtered_results, 1):
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

            print(f"  {rank}. Score: {hit.score:.4f} ({hit.score*100:.1f}%)")
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
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Search for similar faces in Qdrant collection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic search (default collection, top 5 results, no threshold)
  uv run python face_search.py query.jpg

  # Search with custom number of results
  uv run python face_search.py query.jpg --limit 10

  # Search in specific collection with 80% similarity threshold
  uv run python face_search.py query.jpg -c wedding_photos -t 80

  # Search with all options
  uv run python face_search.py query.jpg -c my_faces -l 20 -t 75

  # Short form
  uv run python face_search.py s.jpg -c event_photos -l 5 -t 70
        """
    )

    parser.add_argument(
        'image_path',
        type=str,
        help='Path to the query image'
    )

    parser.add_argument(
        '--collection', '-c',
        type=str,
        default='face_embeddings',
        help='Qdrant collection name (default: face_embeddings)'
    )

    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=5,
        help='Maximum number of results to return (default: 5)'
    )

    parser.add_argument(
        '--threshold', '-t',
        type=float,
        default=0.0,
        help='Minimum similarity threshold as percentage 0-100 (default: 0, no filtering). E.g., 75 means 75%% similarity'
    )

    args = parser.parse_args()

    # Verify image exists
    if not Path(args.image_path).exists():
        print(f"Error: Image not found at {args.image_path}")
        sys.exit(1)

    # Convert percentage to 0-1 range if needed
    threshold = args.threshold / 100.0 if args.threshold > 1.0 else args.threshold

    # Validate threshold range
    if threshold < 0.0 or threshold > 1.0:
        print(f"Error: Threshold must be between 0 and 100 (or 0.0 to 1.0)")
        sys.exit(1)

    # Search for faces
    results = search_faces_in_image(
        args.image_path,
        collection_name=args.collection,
        top_k=args.limit,
        threshold=threshold
    )

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total faces detected in query image: {len(results)}")
    print(f"Collection searched: {args.collection}")
    print(f"Similarity threshold: {threshold*100:.1f}%")
    total_matches = sum(len(r['matches']) for r in results)
    print(f"Total matches found: {total_matches}")
    print(f"{'='*60}")
