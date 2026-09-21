from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import hashlib
import os
import redis
import json
from database import get_db
from models import User, AnalysisJob, Organization, AuditLog
from auth import get_current_user
import librosa
import numpy as np

router = APIRouter()
redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_BUCKET = os.getenv("S3_BUCKET", "voice-integrity")
INFERENCE_URL = os.getenv("INFERENCE_URL", "http://localhost:8001")

@router.post("/analyze")
async def upload_and_analyze(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Upload audio file and enqueue for analysis."""
    
    user_id = current_user["user_id"]
    org_id = current_user["org_id"]
    
    try:
        # 1. Check file size (5MB max for localhost)
        file_content = await file.read()
        if len(file_content) > 5_000_000:  # 5MB
            raise HTTPException(status_code=400, detail="File too large (max 5MB)")
        
        # 2. Check quota
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        org = db.query(Organization).filter(Organization.id == org_id).first()
        
        # Get usage this month
        quota_key = f"quota:{org_id}:{datetime.utcnow().strftime('%Y-%m')}"
        usage_count = redis_client.get(quota_key) or 0
        
        if int(usage_count) >= org.quota_monthly:
            raise HTTPException(status_code=429, detail="Monthly quota exceeded")
        
        # 3. Hash file
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        # 4. Load audio with librosa to validate + get duration
        try:
            import io
            audio_buffer = io.BytesIO(file_content)
            audio_data, sr = librosa.load(audio_buffer, sr=16000, mono=True)
            duration_ms = int((len(audio_data) / sr) * 1000)
            
            if duration_ms > 300_000:  # 5 minutes
                raise HTTPException(status_code=400, detail="Audio too long (max 5 min)")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid audio file: {str(e)}")
        
        # 5. Save to local file system (for localhost development)
        upload_dir = f"/data/uploads/{org_id}/{user_id}"
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = f"{upload_dir}/{file_hash}.wav"
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # 6. Create job record
        job = AnalysisJob(
            user_id=user_id,
            org_id=org_id,
            audio_file_path=file_path,
            audio_file_hash=file_hash,
            audio_duration_ms=duration_ms,
            sample_rate=16000,
            file_size_bytes=len(file_content),
            source="upload",
            status="queued",
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        
        # 7. Enqueue to Redis queue
        queue_data = {
            "job_id": job.id,
            "user_id": user_id,
            "org_id": org_id,
            "audio_file_path": file_path,
            "timestamp": datetime.utcnow().isoformat()
        }
        redis_client.rpush("analysis_queue", json.dumps(queue_data))
        
        # 8. Increment quota
        redis_client.incr(quota_key)
        redis_client.expire(quota_key, 86400 * 35)  # expires after month
        
        # 9. Audit log
        audit = AuditLog(
            org_id=org_id,
            user_id=user_id,
            action="upload",
            resource_type="job",
            resource_id=job.id,
            ip_address=request.client.host if request else None,
            status_code=200
        )
        db.add(audit)
        db.commit()
        
        return {
            "job_id": job.id,
            "status": "queued",
            "message": "Analysis queued successfully",
            "created_at": job.created_at.isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get job status."""
    
    user_id = current_user["user_id"]
    job = db.query(AnalysisJob).filter(
        AnalysisJob.id == job_id,
        AnalysisJob.user_id == user_id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": job.id,
        "status": job.status,
        "created_at": job.created_at.isoformat(),
        "processing_started_at": job.processing_started_at.isoformat() if job.processing_started_at else None,
        "processing_ended_at": job.processing_ended_at.isoformat() if job.processing_ended_at else None,
        "error_message": job.error_message
    }