from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any
import requests
import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# --- App Initialization ---
app = FastAPI(
    title="User & Media Management Service",
    description="Handles user accounts, groups, uploads, and permissions.",
    version="1.0.0",
)

# --- Environment Variables ---
load_dotenv()
FACE_PROCESSING_SERVICE_URL = os.getenv("FACE_PROCESSING_SERVICE_URL", "http://localhost:8000")
FIREBASE_SERVICE_ACCOUNT_KEY = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY", "path/to/your/serviceAccountKey.json")

# --- Firebase Initialization ---
try:
    cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_KEY)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase initialized successfully.")
except Exception as e:
    print(f"Error initializing Firebase: {e}. Please ensure FIREBASE_SERVICE_ACCOUNT_KEY is set correctly.")
    db = None # Set db to None if initialization fails

# --- Pydantic Models ---
class RegisterRequest(BaseModel):
    name: str
    phone_number: str
    otp: str # Placeholder for OTP validation

class RegisterResponse(BaseModel):
    user_id: str
    name: str
    message: str

# --- API Endpoints ---
@app.get("/", tags=["Health Check"])
async def read_root():
    return {"status": "ok", "message": "User & Media Management Service is running."}

@app.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED, tags=["User Management"])
async def register_user(
    name: str = Form(...),
    phone_number: str = Form(...),
    otp: str = Form(...),
    selfie: UploadFile = File(...)
):
    # 1. Validate OTP (Placeholder)
    if otp != "123456": # Simple placeholder OTP
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")

    # 2. Call Face Processing Service to get selfie embedding
    selfie_bytes = await selfie.read()
    files = {'image': (selfie.filename, selfie_bytes, selfie.content_type)}
    
    try:
        # Use the async-embedding endpoint for non-blocking processing
        response = requests.post(f"{FACE_PROCESSING_SERVICE_URL}/async-embedding", files=files)
        response.raise_for_status() # Raise an exception for HTTP errors
        job_response = response.json()
        job_id = job_response["job_id"]

        # Poll for the result (this will block, but for registration, it might be acceptable)
        # In a real-world scenario, this would be handled asynchronously with webhooks or client-side polling
        result_data = None
        for _ in range(30): # Poll for up to 30 seconds
            time.sleep(1)
            result_response = requests.get(f"{FACE_PROCESSING_SERVICE_URL}/results/{job_id}")
            result_response.raise_for_status()
            result_json = result_response.json()
            if result_json["status"] == "complete":
                result_data = result_json["result"]
                break
        
        if not result_data:
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Face processing timed out.")
        
        if not result_data["faces"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No face detected in selfie.")
        
        # Assuming one face per selfie for registration
        selfie_embedding = result_data["faces"][0]["embedding"]

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Face processing service unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing selfie: {e}")

    # 3. Store User Data in Firebase
    if db is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Firebase not initialized.")

    try:
        user_ref = db.collection("users").document()
        user_id = user_ref.id
        user_data = {
            "name": name,
            "phone_number": phone_number,
            "selfie_embedding": selfie_embedding, # Store the embedding
            "created_at": firestore.SERVER_TIMESTAMP
        }
        user_ref.set(user_data)
        print(f"User {user_id} registered successfully.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error saving user data: {e}")

    return {"user_id": user_id, "name": name, "message": "User registered successfully."}


class CreateGroupRequest(BaseModel):
    group_name: str
    description: str = ""

class CreateGroupResponse(BaseModel):
    group_id: str
    group_name: str
    message: str

@app.post("/create-group", response_model=CreateGroupResponse, status_code=status.HTTP_201_CREATED, tags=["Group Management"])
async def create_group(request: CreateGroupRequest):
    if db is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Firebase not initialized.")

    try:
        group_ref = db.collection("groups").document()
        group_id = group_ref.id
        group_data = {
            "group_name": request.group_name,
            "description": request.description,
            "created_at": firestore.SERVER_TIMESTAMP
        }
        group_ref.set(group_data)
        print(f"Group {group_id} created successfully.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creating group: {e}")

    return {"group_id": group_id, "group_name": request.group_name, "message": "Group created successfully."}