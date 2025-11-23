import sys
from pathlib import Path
from face_embedding_processor import FaceEmbeddingProcessor


def search_face_ids(image_path, top_k=5, min_similarity=0.0):
    """
    Search for all faces in an image and return matching face IDs from Qdrant

    Args:
        image_path: Path to the query image
        top_k: Number of similar faces to return for each detected face
        min_similarity: Minimum similarity threshold (0.0-1.0)

    Returns:
        List of dictionaries with face IDs for each detected face:
        [
            {
                'query_face_index': 0,
                'matching_face_ids': ['uuid1', 'uuid2', ...],
                'matching_person_ids': [123, 456, ...],
                'similarity_scores': [0.95, 0.89, ...]
            },
            ...
        ]
    """
    print(f"Processing image: {image_path}")
    print(f"{'='*60}")

    # Initialize processor
    processor = FaceEmbeddingProcessor(collection_name="face_embeddings")

    # Extract faces and embeddings from the query image
    face_data, error_message = processor.extract_face_embeddings(Path(image_path))

    if not face_data:
        print(f"✗ No faces found in the image! {error_message if error_message else ''}")
        return []

    print(f"✓ Found {len(face_data)} face(s) in the image\n")

    all_results = []

    # Search for each face
    for idx, face in enumerate(face_data):
        print(f"Face {idx + 1}:")

        # Search for similar faces in Qdrant
        search_results = processor.client.query_points(
            collection_name=processor.collection_name,
            query=face['embedding'].tolist(),
            limit=top_k
        ).points

        # Filter by similarity threshold
        matching_face_ids = []
        matching_person_ids = []
        similarity_scores = []

        for hit in search_results:
            if hit.score >= min_similarity:
                matching_face_ids.append(hit.payload['face_id'])
                matching_person_ids.append(hit.payload.get('person_id', None))
                similarity_scores.append(hit.score)

        print(f"  ✓ Found {len(matching_face_ids)} matches (similarity >= {min_similarity})")

        all_results.append({
            'query_face_index': idx,
            'matching_face_ids': matching_face_ids,
            'matching_person_ids': matching_person_ids,
            'similarity_scores': similarity_scores
        })

    return all_results


def get_all_face_ids_flat(image_path, top_k=5, min_similarity=0.0):
    """
    Get a flat list of all matching face IDs across all detected faces

    Args:
        image_path: Path to the query image
        top_k: Number of similar faces to return for each detected face
        min_similarity: Minimum similarity threshold (0.0-1.0)

    Returns:
        List of unique face IDs (strings) across all detected faces
    """
    results = search_face_ids(image_path, top_k, min_similarity)

    # Collect all face IDs
    all_face_ids = []
    for result in results:
        all_face_ids.extend(result['matching_face_ids'])

    # Remove duplicates while preserving order
    unique_face_ids = list(dict.fromkeys(all_face_ids))

    return unique_face_ids


def get_face_ids_by_person(image_path, top_k=5, min_similarity=0.0):
    """
    Get matching face IDs grouped by person_id

    Args:
        image_path: Path to the query image
        top_k: Number of similar faces to return for each detected face
        min_similarity: Minimum similarity threshold (0.0-1.0)

    Returns:
        Dictionary mapping person_id to list of face IDs:
        {
            123: ['face_id_1', 'face_id_2'],
            456: ['face_id_3'],
            None: ['face_id_4']  # Unclustered faces
        }
    """
    results = search_face_ids(image_path, top_k, min_similarity)

    # Group by person_id
    person_groups = {}
    for result in results:
        for face_id, person_id in zip(result['matching_face_ids'], result['matching_person_ids']):
            if person_id not in person_groups:
                person_groups[person_id] = []
            if face_id not in person_groups[person_id]:  # Avoid duplicates
                person_groups[person_id].append(face_id)

    return person_groups


if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python face_search_ids.py <image_path> [top_k] [min_similarity] [--grouped]")
        print("\nArguments:")
        print("  image_path      Path to the query image")
        print("  top_k           Number of matches per face (default: 5)")
        print("  min_similarity  Minimum similarity score 0.0-1.0 (default: 0.0)")
        print("  --grouped       Group results by person_id")
        print("  --flat          Return flat list of unique face IDs (default)")
        print("\nExamples:")
        print("  python face_search_ids.py query.jpg")
        print("  python face_search_ids.py query.jpg 10")
        print("  python face_search_ids.py query.jpg 10 0.8")
        print("  python face_search_ids.py query.jpg 10 0.8 --grouped")
        sys.exit(1)

    image_path = sys.argv[1]
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 5
    min_similarity = float(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].replace('.', '').isdigit() else 0.0

    # Check for output format flags
    grouped = '--grouped' in sys.argv
    flat = '--flat' in sys.argv or not grouped  # Default to flat

    # Verify image exists
    if not Path(image_path).exists():
        print(f"✗ Error: Image not found at {image_path}")
        sys.exit(1)

    print(f"Settings: top_k={top_k}, min_similarity={min_similarity}")
    print()

    if grouped:
        # Get results grouped by person
        results = get_face_ids_by_person(image_path, top_k, min_similarity)

        print(f"\n{'='*60}")
        print("RESULTS (Grouped by Person)")
        print(f"{'='*60}")

        for person_id, face_ids in results.items():
            person_label = f"Person {person_id}" if person_id is not None else "Unclustered"
            print(f"\n{person_label}:")
            print(f"  Face IDs: {face_ids}")
            print(f"  Count: {len(face_ids)}")

        print(f"\n{'='*60}")
        print(f"Total persons: {len(results)}")
        total_faces = sum(len(ids) for ids in results.values())
        print(f"Total unique face IDs: {total_faces}")
        print(f"{'='*60}")

    else:
        # Get flat list of unique face IDs
        face_ids = get_all_face_ids_flat(image_path, top_k, min_similarity)

        print(f"\n{'='*60}")
        print("RESULTS (Flat List)")
        print(f"{'='*60}")
        print(f"\nMatching Face IDs:")
        for i, face_id in enumerate(face_ids, 1):
            print(f"  {i}. {face_id}")

        print(f"\n{'='*60}")
        print(f"Total unique face IDs: {len(face_ids)}")
        print(f"{'='*60}")
