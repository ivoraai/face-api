from face_embedding_processor import FaceEmbeddingProcessor


if __name__ == "__main__":
    # Initialize processor
    processor = FaceEmbeddingProcessor(collection_name="face_embeddings")

    # Reset the collection (delete all old data)
    print("Resetting collection...")
    processor.reset_collection()

    # Re-index only the dir folder (not .venv or other system folders)
    image_directory = "./dir"

    print(f"\nProcessing images from: {image_directory}")
    stats = processor.process_directory(image_directory)

    print(f"\n{'='*50}")
    print("Re-indexing Complete:")
    print(f"{'='*50}")
    print(f"Total images found: {stats['total_images']}")
    print(f"Successfully processed: {stats['processed_images']}")
    print(f"Failed to process: {stats['failed_images']}")
    print(f"Total faces indexed: {stats['total_faces']}")
    print(f"{'='*50}")
