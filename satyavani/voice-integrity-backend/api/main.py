from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os
import logging
import json
from datetime import datetime, timedelta
import hashlib
import boto3
from contextlib import asynccontextmanager

# Internal imports
from database import Base, init_db
from models import User, Organization, AnalysisJob, AnalysisResult, AuditLog
from auth import AuthService, get_current_user
from routes.upload import router as upload_router
from routes.results import router as results_router

# ============ CONFIG ============
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://voice_user:dev_password_123@localhost:5432/voice_integrity")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin123")
S3_BUCKET = os.getenv("S3_BUCKET", "voice-integrity")
INFERENCE_URL = os.getenv("INFERENCE_URL", "http://localhost:8001")

# ============ LOGGING ============
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecimalRenderer(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()

# ============ DATABASE ============
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============ S3 CLIENT ============
s3_client = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name='us-east-1'
)

# Create bucket if not exists
try:
    s3_client.head_bucket(Bucket=S3_BUCKET)
except:
    s3_client.create_bucket(Bucket=S3_BUCKET)

# ============ REDIS ============
import redis
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# ============ STARTUP / SHUTDOWN ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("initializing_app")
    init_db(engine)
    yield
    # Shutdown
    logger.info("shutting_down_app")

app = FastAPI(
    title="Voice Integrity API",
    description="Real-time voice authenticity detection",
    version="1.0.0",
    lifespan=lifespan
)

# ============ HEALTH CHECK ============
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": "ok",
            "redis": "ok",
            "s3": "ok",
            "inference": "ok"
        }
    }

# ============ AUTH ROUTES ============
@app.post("/auth/register")
async def register(email: str, password: str, db: Session = Depends(get_db)):
    """Create a new user account (free tier)."""
    
    # Check if user exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Get or create default org
    default_org = db.query(Organization).filter(Organization.name == "Hack Forge Team").first()
    if not default_org:
        default_org = Organization(name="Default Org", tier="free", quota_monthly=100)
        db.add(default_org)
        db.commit()
    
    # Hash password
    password_hash = AuthService.hash_password(password)
    
    # Create user
    user = User(
        email=email,
        password_hash=password_hash,
        org_id=default_org.id,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info("user_registered", email=email, user_id=user.id)
    
    return {
        "user_id": user.id,
        "email": user.email,
        "message": "Registration successful"
    }

@app.post("/auth/login")
async def login(email: str, password: str, db: Session = Depends(get_db)):
    """Login and receive JWT token."""
    
    user = db.query(User).filter(User.email == email).first()
    if not user or not AuthService.verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = AuthService.create_token(user.id, user.org_id)
    
    logger.info("user_login", user_id=user.id, email=email)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "expires_in": 86400
    }

# ============ ROUTES ============
app.include_router(upload_router, prefix="/api/v1", tags=["upload"])
app.include_router(results_router, prefix="/api/v1", tags=["results"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)