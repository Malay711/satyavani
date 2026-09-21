from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import AnalysisJob, AnalysisResult, EvidenceRecord

router = APIRouter()

@router.get("/jobs/{job_id}/result")
async def get_result(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get analysis result for a completed job."""
    
    user_id = current_user["user_id"]
    
    job = db.query(AnalysisJob).filter(
        AnalysisJob.id == job_id,
        AnalysisJob.user_id == user_id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job status is {job.status}, not completed")
    
    result = db.query(AnalysisResult).filter(AnalysisResult.job_id == job_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    
    evidence = db.query(EvidenceRecord).filter(EvidenceRecord.result_id == result.id).all()
    
    return {
        "job_id": job.id,
        "verdict": result.verdict,
        "authenticity_score": result.authenticity_score,
        "risk_score": result.risk_score,
        "confidence": result.confidence,
        "evidence": [
            {
                "type": ev.evidence_type,
                "label": ev.label,
                "score": ev.score,
                "interpretation": ev.interpretation
            }
            for ev in evidence
        ],
        "model_version": result.model_version,
        "inference_time_ms": result.inference_time_ms,
        "created_at": result.created_at.isoformat()
    }

@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a job and its audio file."""
    
    user_id = current_user["user_id"]
    
    job = db.query(AnalysisJob).filter(
        AnalysisJob.id == job_id,
        AnalysisJob.user_id == user_id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Delete audio file
    if os.path.exists(job.audio_file_path):
        os.remove(job.audio_file_path)
    
    # Mark as deleted
    job.deleted_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Job deleted successfully"}