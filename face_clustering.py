import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score
from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


class FaceClusterer:
    """Face clustering for person identification across images"""

    def __init__(self, collection_name="face_embeddings", similarity_threshold=0.80):
        """
        Initialize face clusterer

        Args:
            collection_name: Qdrant collection name
            similarity_threshold: Minimum cosine similarity for same person (0-1)
                                 0.80 = balanced precision/recall
                                 0.85 = high precision (strict)
                                 0.70 = high recall (loose)
        """
        # Initialize Qdrant client
        self.qdrant_url = os.getenv("QDRANT_URL", "localhost")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY", None)

        if self.qdrant_api_key:
            self.client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key)
        else:
            self.client = QdrantClient(host=self.qdrant_url, port=self.qdrant_port)

        self.collection_name = collection_name
        self.similarity_threshold = similarity_threshold
        # DBSCAN uses distance, so eps = 1 - similarity
        self.dbscan_eps = 1.0 - similarity_threshold

    def get_all_embeddings(self):
        """
        Retrieve all face embeddings from Qdrant

        Returns:
            embeddings: numpy array of shape (n, 512)
            point_ids: list of Qdrant point IDs
            payloads: list of payload dicts
        """
        all_points = []
        offset = None
        batch_size = 1000

        print(f"Retrieving embeddings from collection '{self.collection_name}'...")

        while True:
            result = self.client.scroll(
                collection_name=self.collection_name,
                limit=batch_size,
                offset=offset,
                with_vectors=True,
                with_payload=True
            )

            points, next_offset = result
            all_points.extend(points)

            if next_offset is None:
                break
            offset = next_offset

        # Extract data
        embeddings = np.array([point.vector for point in all_points])
        point_ids = [point.id for point in all_points]
        payloads = [point.payload for point in all_points]

        print(f"Retrieved {len(embeddings)} face embeddings")

        return embeddings, point_ids, payloads

    def compute_cosine_similarities(self, embeddings):
        """
        Compute cosine similarity matrix

        Args:
            embeddings: numpy array of shape (n, 512)

        Returns:
            similarity_matrix: numpy array of shape (n, n)
        """
        # Normalize embeddings
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        normalized = embeddings / norms

        # Compute similarity matrix (dot product of normalized vectors)
        similarity_matrix = np.dot(normalized, normalized.T)

        return similarity_matrix

    def cluster_faces(self, embeddings):
        """
        Cluster faces using DBSCAN

        Args:
            embeddings: numpy array of shape (n, 512)

        Returns:
            cluster_labels: numpy array of cluster IDs
                           -1 indicates outlier (unique person)
        """
        print(f"Clustering faces with DBSCAN (threshold={self.similarity_threshold})...")

        # Compute distance matrix (1 - cosine similarity)
        similarity_matrix = self.compute_cosine_similarities(embeddings)
        distance_matrix = 1.0 - similarity_matrix

        # Clip to ensure non-negative (handle numerical precision issues)
        distance_matrix = np.clip(distance_matrix, 0, None)

        # Run DBSCAN
        # eps: maximum distance between samples in same cluster
        # min_samples: minimum cluster size (1 = allow single-face persons)
        # metric: 'precomputed' since we provide distance matrix
        dbscan = DBSCAN(eps=self.dbscan_eps, min_samples=1, metric='precomputed')
        cluster_labels = dbscan.fit_predict(distance_matrix)

        # Assign unique person IDs to outliers (label -1)
        outliers = cluster_labels == -1
        if np.any(outliers):
            max_label = cluster_labels.max()
            unique_ids = np.arange(max_label + 1, max_label + 1 + outliers.sum())
            cluster_labels[outliers] = unique_ids

        n_clusters = len(set(cluster_labels))
        print(f"Found {n_clusters} unique persons")

        return cluster_labels

    def evaluate_clustering_quality(self, embeddings, cluster_labels):
        """
        Compute clustering quality metrics

        Args:
            embeddings: numpy array of shape (n, 512)
            cluster_labels: numpy array of cluster IDs

        Returns:
            metrics: dict with quality scores
        """
        n_faces = len(embeddings)
        n_persons = len(set(cluster_labels))

        # Compute cluster sizes
        unique_labels, counts = np.unique(cluster_labels, return_counts=True)
        avg_faces_per_person = np.mean(counts)
        max_faces_per_person = np.max(counts)
        single_face_persons = np.sum(counts == 1)

        # Compute silhouette score (if more than 1 cluster)
        silhouette = 0.0
        if n_persons > 1:
            try:
                silhouette = silhouette_score(embeddings, cluster_labels)
            except:
                silhouette = 0.0

        # Compute cluster purity (average intra-cluster similarity)
        purities = []
        for label in unique_labels:
            cluster_mask = cluster_labels == label
            cluster_embeddings = embeddings[cluster_mask]

            if len(cluster_embeddings) > 1:
                # Compute pairwise similarities within cluster
                norms = np.linalg.norm(cluster_embeddings, axis=1, keepdims=True)
                normalized = cluster_embeddings / norms
                sim_matrix = np.dot(normalized, normalized.T)

                # Get upper triangle (excluding diagonal)
                sim_values = sim_matrix[np.triu_indices_from(sim_matrix, k=1)]
                purities.append(np.mean(sim_values))

        avg_purity = np.mean(purities) if purities else 1.0

        metrics = {
            'total_faces': n_faces,
            'total_persons': n_persons,
            'avg_faces_per_person': float(avg_faces_per_person),
            'max_faces_per_person': int(max_faces_per_person),
            'single_face_persons': int(single_face_persons),
            'silhouette_score': float(silhouette),
            'avg_cluster_purity': float(avg_purity)
        }

        return metrics

    def update_person_ids(self, point_ids, person_ids):
        """
        Update Qdrant with person_id assignments

        Args:
            point_ids: list of Qdrant point IDs
            person_ids: list of person_id assignments (same order)
        """
        print(f"Updating {len(point_ids)} faces with person_id...")

        # Group point IDs by person_id for efficient batch updates
        # This reduces API calls from O(n_faces) to O(n_persons)
        person_groups = {}
        for point_id, person_id in zip(point_ids, person_ids):
            person_id = int(person_id)
            if person_id not in person_groups:
                person_groups[person_id] = []
            person_groups[person_id].append(point_id)

        # Prepare common payload fields
        timestamp = datetime.now().isoformat()

        total_persons = len(person_groups)
        print(f"Updating in {total_persons} batches (one per person)...")

        # Update each person's faces in a single batch
        successful_updates = 0
        failed_updates = 0

        for idx, (person_id, point_list) in enumerate(person_groups.items(), 1):
            try:
                self.client.set_payload(
                    collection_name=self.collection_name,
                    payload={
                        "person_id": person_id,
                        "cluster_timestamp": timestamp,
                        "cluster_threshold": self.similarity_threshold
                    },
                    points=point_list
                )
                successful_updates += len(point_list)

                # Progress indicator every 100 persons
                if idx % 100 == 0 or idx == total_persons:
                    print(f"  Progress: {idx}/{total_persons} persons ({successful_updates} faces updated)")

            except Exception as e:
                failed_updates += len(point_list)
                print(f"  ✗ Failed to update person {person_id} ({len(point_list)} faces): {e}")
                continue

        print(f"✓ Update complete: {successful_updates} faces updated, {failed_updates} failed")

    def run_full_clustering(self):
        """
        Run complete clustering pipeline

        Returns:
            metrics: clustering quality metrics
        """
        # Step 1: Get all embeddings
        embeddings, point_ids, payloads = self.get_all_embeddings()

        if len(embeddings) == 0:
            print("No faces found in collection")
            return None

        # Step 2: Cluster faces
        person_ids = self.cluster_faces(embeddings)

        # Step 3: Evaluate quality
        metrics = self.evaluate_clustering_quality(embeddings, person_ids)

        # Step 4: Update Qdrant
        self.update_person_ids(point_ids, person_ids)

        # Step 5: Print summary
        self.print_clustering_summary(metrics)

        return metrics

    def print_clustering_summary(self, metrics):
        """Print formatted clustering summary"""
        print(f"\n{'='*60}")
        print("CLUSTERING SUMMARY")
        print(f"{'='*60}")
        print(f"Total faces:              {metrics['total_faces']}")
        print(f"Unique persons:           {metrics['total_persons']}")
        print(f"Avg faces/person:         {metrics['avg_faces_per_person']:.2f}")
        print(f"Max faces/person:         {metrics['max_faces_per_person']}")
        print(f"Single-face persons:      {metrics['single_face_persons']}")
        print(f"Silhouette score:         {metrics['silhouette_score']:.3f} (>0.5 is good)")
        print(f"Avg cluster purity:       {metrics['avg_cluster_purity']:.3f} (>0.8 is good)")
        print(f"Similarity threshold:     {self.similarity_threshold}")
        print(f"{'='*60}\n")

    def find_similar_faces(self, query_embedding, top_k=10):
        """
        Find most similar faces to query embedding

        Args:
            query_embedding: numpy array of shape (512,)
            top_k: number of results to return

        Returns:
            results: list of (person_id, similarity_score, payload)
        """
        # Search in Qdrant
        search_results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding.tolist(),
            limit=top_k
        ).points

        # Extract results
        results = []
        for hit in search_results:
            person_id = hit.payload.get('person_id', None)
            results.append({
                'person_id': person_id,
                'similarity': hit.score,
                'image_path': hit.payload['image_path'],
                'face_id': hit.payload['face_id']
            })

        return results


if __name__ == "__main__":
    # Example usage
    clusterer = FaceClusterer(
        collection_name="face_embeddings",
        similarity_threshold=0.80
    )

    # Run clustering
    metrics = clusterer.run_full_clustering()

    if metrics:
        print("Clustering completed successfully!")
