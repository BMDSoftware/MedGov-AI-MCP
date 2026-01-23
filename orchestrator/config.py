# Backend Configuration
import os
from dotenv import load_dotenv

load_dotenv()

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5001"))

# CORS Configuration
CORS_ORIGINS = [
    "http://localhost:5173",  # Vite default
    "http://localhost:3000",  # React default
    os.getenv("FRONTEND_URL", "")
]
CORS_ORIGINS = [origin for origin in CORS_ORIGINS if origin]  # Filter empty strings
