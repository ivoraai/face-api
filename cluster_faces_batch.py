#!/usr/bin/env python3
"""
Batch Face Clustering Script

Runs DBSCAN clustering on all faces in Qdrant collection
and assigns person_id to group same individuals across images.

Usage:
    python cluster_faces_batch.py [--threshold 0.80]
"""

import sys
import argparse
from face_clustering import FaceClusterer


def main():
    parser = argparse.ArgumentParser(description='Batch face clustering')
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.80,
        help='Cosine similarity threshold (0-1). Default: 0.80. Higher = stricter matching.'
    )
    parser.add_argument(
        '--collection',
        type=str,
        default='face_embeddings',
        help='Qdrant collection name. Default: face_embeddings'
    )

    args = parser.parse_args()

    print("="*60)
    print("BATCH FACE CLUSTERING")
    print("="*60)
    print(f"Collection: {args.collection}")
    print(f"Similarity threshold: {args.threshold}")
    print("="*60 + "\n")

    # Initialize clusterer
    clusterer = FaceClusterer(
        collection_name=args.collection,
        similarity_threshold=args.threshold
    )

    # Run clustering
    try:
        metrics = clusterer.run_full_clustering()

        if metrics:
            print("\n✓ Clustering completed successfully!")
            print(f"✓ Assigned person_id to {metrics['total_faces']} faces")
            print(f"✓ Identified {metrics['total_persons']} unique persons")

            # Quality assessment
            if metrics['silhouette_score'] > 0.5:
                print(f"✓ Quality: GOOD (silhouette={metrics['silhouette_score']:.3f})")
            elif metrics['silhouette_score'] > 0.3:
                print(f"⚠ Quality: FAIR (silhouette={metrics['silhouette_score']:.3f})")
            else:
                print(f"⚠ Quality: POOR (silhouette={metrics['silhouette_score']:.3f})")
                print("  Consider adjusting threshold or reviewing data quality")

            return 0
        else:
            print("⚠ No faces found in collection")
            return 1

    except Exception as e:
        print(f"✗ Error during clustering: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
