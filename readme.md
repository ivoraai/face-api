⏺ Here are the key commands to use:

  1. Search for faces (now shows person_id):
  uv run python face_search.py s.jpg 5

  2. Re-run clustering (if you add more images):
  uv run python cluster_faces_batch.py --threshold 0.80

  3. Add new images to database:
  uv run python face_embedding_processor.py
  (Edit line 264 to change image directory)

  4. Search with different image:
  uv run python face_search.py dir/img.JPG 10

  ---
  Most Common Use Case:
  # Search for similar faces - now with person_id!
  uv run python face_search.py s.jpg 5

  This will show:
  - Similarity scores
  - Person ID (same person = same ID across all images!)
  - Image paths
  - Face IDs within each image

  Try it now! 🚀