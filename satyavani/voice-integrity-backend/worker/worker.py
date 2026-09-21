import redis
import json
import time
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import librosa
import numpy as np
import requests

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ CONFIG ============
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
INFERENCE_URL = os.getenv("INFERENCE_URL", "http://localhost:8001")

# Database
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Redis
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# ============ MODELS (import from API) ============
from models import AnalysisJob, AnalysisResult, EvidenceRecord

def extract_features(audio_path):
    """Extract comprehensive audio features."""
    
    audio, sr = librosa.load(audio_path, sr=16000, mono=True)
    
    # Acoustic features
    rms = librosa.feature.rms(y=audio)
    zcr = librosa.feature.zero_crossing_rate(audio)
    spectral_centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)
    
    # Prosody
    f0 = librosa.yin(audio, fmin=80, fmax=400)  # fundamental frequency
    voiced_ratio = np.mean(f0 > 0)
    
    # Spectral
    melspec = librosa.feature.melspectrogram(y=audio, sr=sr, n_mels=128)
    mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
    chroma = librosa.feature.chroma_cens(y=audio, sr=sr)
    
    return {
        'acoustic': {
            'rms_mean': float(rms.mean()),
            'rms_std': float(rms.std()),
            'zcr_mean': float(zcr.mean()),
            'zcr_std': float(zcr.std()),
            'spectral_centroid_mean': float(spectral_centroid.mean()),
        },
        'prosody': {
            'voiced_ratio': float(voiced_ratio),
            'f0_mean': float(f0[f0 > 0].mean()) if np.any(f0 > 0) else 0.0,
        },
        'spectral': {
            'melspec_mean': float(melspec.mean()),
            'mfcc_mean': float(mfcc.mean()),
            'chroma_mean': float(chroma.mean()),
        }
    }

def analyze_audio(job_id: int):
    """Main analysis pipeline."""
    
    db = SessionLocal()
    
    try:
        logger.info(f"Starting analysis for job {job_id}")
        
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        # Update status
        job.status = "processing"
        job.processing_started_at = datetime.utcnow()
        db.commit()
        
        # 1. Extract features
        logger.info(f"Extracting features from {job.audio_file_path}")
        features = extract_features(job.audio_file_path)
        
        # 2. Call inference service
        logger.info(f"Calling inference service")
        response = requests.post(
            f"{INFERENCE_URL}/predict",
            json={"audio_path": job.audio_file_path},
            timeout=60
        )
        
        if response.status_code != 200:
            raise Exception(f"Inference failed: {response.text}")
        
        pred = response.json()
        
        # 3. Generate evidence
        evidence_list = [
            {
                "type": "anti_spoof",
                "label": "Anti-spoof model",
                "score": pred['score'],
                "level": "High" if pred['score'] > 70 else "Moderate" if pred['score'] > 40 else "Low"
            },
            {
                "type": "temporal_consistency",
                "label": "Temporal consistency",
                "score": max(0, min(100, features['prosody'].get('voiced_ratio', 0.5) * 100)),
                "level": "Strong" if features['prosody']['voiced_ratio'] > 0.6 else "Moderate"
            },
            {
                "type": "spectral",
                "label": "Spectral analysis",
                "score": max(0, min(100, 60 + features['acoustic']['zcr_mean'] * 20)),
                "level": "Moderate"
            }
        ]
        
        # 4. Create result
        result = AnalysisResult(
            job_id=job_id,
            verdict=pred['verdict'],
            authenticity_score=pred['score'],
            risk_score=100 - pred['score'],
            confidence=pred['confidence'],
            anti_spoof_score=pred['score'],
            temporal_consistency=evidence_list[1]['score'],
            spectral_score=evidence_list[2]['score'],
            replay_indicator=max(0, 100 - pred['score']) if pred['verdict'] == 'synthetic' else 0,
            model_version="aasist-v1.0",
            inference_time_ms=int(pred['inference_time_ms']),
            feature_data=features,
            risk_timeline=generate_risk_timeline(pred['score'])
        )
        db.add(result)
        db.flush()
        
        # 5. Add evidence records
        for ev in evidence_list:
            evidence_record = EvidenceRecord(
                result_id=result.id,
                evidence_type=ev['type'],
                label=ev['label'],
                score=ev['score'],
                interpretation=ev['level'].lower()
            )
            db.add(evidence_record)
        
        # 6. Mark job complete
        job.status = "completed"
        job.processing_ended_at = datetime.utcnow()
        
        db.commit()
        logger.info(f"Analysis complete for job {job_id}: {pred['verdict']}")
    
    except Exception as e:
        logger.error(f"Analysis failed for job {job_id}: {str(e)}")
        job.status = "failed"
        job.error_message = str(e)
        db.commit()
    
    finally:
        db.close()

def generate_risk_timeline(score):
    """Generate mock risk timeline for UI."""
    # In real system, this would be computed throughout the analysis
    timeline = []
    for i in range(0, 100, 10):
        risk = 100 - score + np.random.randint(-5, 5)
        timeline.append({"time_ms": i * 300, "risk": max(0, min(100, risk))})
    return timeline

def worker_loop():
    """Continuously process jobs from queue."""
    
    logger.info("Worker starting...")
    
    while True:
        try:
            # Block until a job arrives (timeout every 10s to avoid hanging)
            result = redis_client.blpop("analysis_queue", timeout=10)
            
            if not result:
                continue
            
            queue_name, job_json = result
            job_data = json.loads(job_json)
            job_id = job_data['job_id']
            
            logger.info(f"Processing job {job_id}")
            analyze_audio(job_id)
        
        except Exception as e:
            logger.error(f"Worker error: {str(e)}")
            time.sleep(5)

if __name__ == "__main__":
    worker_loop()