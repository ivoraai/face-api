Your requirements logically split into two main services:


   1. Face Processing Service: A specialized, stateless AI service responsible for all computer vision tasks. It takes an
      image and returns data, or it receives a job and processes it. Given the ML requirements, Python is the ideal
      language for this service, using libraries like DeepFace, OpenCV, and Qdrant-client.


   2. User & Media Management Service: A standard backend service that handles user authentication, file uploads, data
      persistence (user profiles, group info), and business logic. It acts as the primary interface for clients and
      orchestrates calls to the Face Processing Service. Go, Node.js, or Python would be suitable here.

  Here is the detailed documentation for both services.

  ---

  1. Face Processing Service


  Description: Handles all core facial detection, feature extraction, embedding generation, and searching. It's designed to
  be a stateless worker service.

  Endpoints


  `POST /get-faces`
   * Description: Detects all faces in a given image and returns them as cropped, base64-encoded strings.
   * Request Body: multipart/form-data with a single field image.
   * Success Response (200 OK):


    1     {
    2       "faces": [
    3         {
    4           "face_id": 0,
    5           "face_b64": "iVBORw0KGgoAAAANSUhEUg...",
    6           "facial_area": {"x": 120, "y": 80, "w": 90, "h": 90},
    7           "confidence": 0.99
    8         }
    9       ]
   10     }

   * Error Response (400 Bad Request): If no image is provided or the file is invalid.


  `POST /get-features`
   * Description: Extracts high-level facial features (landmarks, emotion, age, gender) for each detected face.
   * Request Body: multipart/form-data with a single field image.
   * Success Response (200 OK):


    1     {
    2       "faces": [
    3         {
    4           "face_id": 0,
    5           "facial_area": {"x": 120, "y": 80, "w": 90, "h": 90},
    6           "confidence": 0.99,
    7           "features": {
    8             "emotion": "happy",
    9             "age": 25,
   10             "gender": "Man",
   11             "landmarks": {
   12               "left_eye": [130, 100],
   13               "right_eye": [170, 100],
   14               "nose": [150, 125]
   15             }
   16           }
   17         }
   18       ]
   19     }



  `POST /get-embedding`
   * Description: A comprehensive endpoint that returns detected faces, features, and the raw vector embedding for each
     face.
   * Request Body: multipart/form-data with a single field image.
   * Success Response (200 OK):


    1     {
    2       "faces": [
    3         {
    4           "face_id": 0,
    5           "face_b64": "iVBORw0KGgoAAAANSUhEUg...",
    6           "facial_area": {"x": 120, "y": 80, "w": 90, "h": 90},
    7           "features": { ... },
    8           "embedding": [0.123, -0.456, ..., 0.789]
    9         }
   10       ]
   11     }



  `POST /digest`
   * Description: (Asynchronous) Initiates a long-running background job to process all images from a given S3 location. It
     extracts faces, creates thumbnails, and upserts all relevant data into Qdrant and Firebase.
   * Request Body: application/json


   1     {
   2       "s3_bucket": "my-photo-bucket",
   3       "s3_prefix": "uploads/group-123/",
   4       "group_id": "group-123"
   5     }

   * Success Response (202 Accepted): Immediately returns a job ID for status tracking.


   1     {
   2       "job_id": "digest-xyz-789",
   3       "status": "started",
   4       "message": "Image digestion process has been initiated."
   5     }

   * Analysis: This should use a task queue (e.g., Celery, RabbitMQ) to handle the processing in the background without
     blocking the API.


  `POST /cluster-faces`
   * Description: (Asynchronous) Triggers a clustering job on all faces associated with a group-id. It uses the DBSCAN
     algorithm to identify unique individuals and assigns a person_id to each face embedding in Qdrant.
   * Request Body: application/json

   1     {
   2       "group_id": "group-123"
   3     }

   * Success Response (202 Accepted):


   1     {
   2       "job_id": "cluster-abc-456",
   3       "status": "started",
   4       "message": "Face clustering process has been initiated."
   5     }



  `POST /search-face`
   * Description: Searches for faces in Qdrant that are similar to the face in the provided image.
   * Request Body: multipart/form-data with fields image and confidence (e.g., 0.85).
   * Success Response (200 OK):


    1     {
    2       "matches": [
    3         {
    4           "image_s3_path": "uploads/group-123/photo1.jpg",
    5           "face_id": 2,
    6           "similarity_score": 0.92,
    7           "person_id": 42
    8         }
    9       ]
   10     }


  ---

  2. User & Media Management Service


  Description: Handles user accounts, groups, uploads, permissions, and orchestrates calls to the Face Processing Service.

  Endpoints


  `POST /register`
   * Description: Registers a new user, processes their selfie to create a reference embedding, and stores their profile.
   * Request Body: multipart/form-data with fields name, phone_number, otp, and selfie (image file).
   * Analysis: This endpoint will call the /get-embedding endpoint of the Face Processing Service to get the user's
     reference face embedding.
   * Success Response (201 Created):

   1     {
   2       "user_id": "user-uuid-123",
   3       "name": "John Doe",
   4       "message": "User registered successfully."
   5     }



  `POST /create-group`
   * Description: Creates a new group or event for organizing photos.
   * Request Body: application/json

   1     {
   2       "group_name": "Family Vacation 2025",
   3       "description": "Trip to the mountains."
   4     }

   * Success Response (201 Created):

   1     {
   2       "group_id": "group-abc-789",
   3       "group_name": "Family Vacation 2025"
   4     }



  `POST /upload`
   * Description: Uploads files (or a cloud drive URL) to a specific group. After the upload is complete, it triggers the 
     `/digest` process.
   * Request Body: multipart/form-data with files (multiple) and group_id, OR application/json with drive_url and group_id.
   * Analysis: This is an orchestrator. On completion, it will make an API call to POST /digest on the Face Processing
     Service with the correct S3 path.
   * Success Response (202 Accepted):

   1     {
   2       "message": "Upload complete. Processing has been triggered."
   3     }



  `GET /get`
   * Description: Retrieves images for a user. Behavior changes based on authentication. Returns secure, temporary, signed
     URLs for accessing the images.
   * Query Parameters: user_id or phone_number.
   * Authentication: Requires a JWT token in the Authorization header.
   * Business Logic:
       1. If the JWT indicates an admin role, return all images for the specified group/user.
       2. If not an admin, find the user's reference face embedding and search for all images they appear in.
       3. Also, return any photos designated as "common" for the groups they are part of.
   * Success Response (200 OK):


   1     {
   2       "personal_images": [
   3         {"url": "https://s3.signed.url/photo1.jpg?token=...", "expires": "timestamp"},
   4         {"url": "https://s3.signed.url/photo5.jpg?token=...", "expires": "timestamp"}
   5       ],
   6       "common_images": [
   7         {"url": "https://s3.signed.url/group_photo.jpg?token=...", "expires": "timestamp"}
   8       ]
   9     }



  `/images` (CRUD Operations)
   * Description: Standard CRUD endpoints for managing image metadata. Requires admin privileges.
   * Endpoints:
       * GET /images/{image_id}: Get metadata for a single image.
       * PUT /images/{image_id}: Update image metadata (e.g., tags, description).
       * DELETE /images/{image_id}: Delete an image and its associated data from all systems (S3, Qdrant, Firebase).


  `POST /update-group`
   * Description: Allows an admin to manage group settings, such as designating a set of photos as "common photos" for all
     members.
   * Request Body: application/json


   1     {
   2       "group_id": "group-abc-789",
   3       "common_photo_ids": ["image-uuid-1", "image-uuid-2"]
   4     }

   * Success Response (200 OK):

   1     {
   2       "message": "Group updated successfully."
   3     }



  `POST /download`
   * Description: Creates a downloadable ZIP archive of selected images.
   * Analysis: This is an asynchronous process. It should:
       1. Receive a list of image IDs.
       2. Create a background job to fetch these images from S3.
       3. Create a ZIP file in a temporary S3 location.
       4. Set a 7-day retention policy on the ZIP file.
       5. Return a signed URL to download the generated ZIP file.
   * Request Body: application/json


   1     {
   2       "image_ids": ["image-uuid-1", "image-uuid-2", "image-uuid-3"]
   3     }

   * Success Response (202 Accepted):


   1     {
   2       "job_id": "download-zip-123",
   3       "status": "pending",
   4       "message": "Your download is being prepared. Poll the status endpoint for the URL."
   5     }

