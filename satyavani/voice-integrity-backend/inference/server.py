from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import numpy as np
import librosa
import io
import logging
import time
from datetime import datetime
from aasist_model import AASIST
import os

logger = logging.getLogger(__name__)

# ============ CONFIG ============
DEVICE = os.getenv("MODEL_DEVICE", "cpu")

# ============ APP ============
app = FastAPI(title="Voice Integrity Inference", version="1.0.0")

# Load model once at startup
model = AASIST.load_pretrained(device=DEVICE)

# ============ ROUTES ============
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "device": DEVICE
    }

class PredictRequest(BaseModel):
    audio_path: str  # path to wav file

class PredictResponse(BaseModel):
    score: float  # 0-100
    confidence: float  # 0-100
    verdict: str  # human, synthetic, uncertain
    inference_time_ms: float

@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    """Analyze audio file and return authenticity score."""
    
    try:
        start_time = time.time()
        
        # 1. Load audio
        if not os.path.exists(request.audio_path):
            raise FileNotFoundError(f"Audio file not found: {request.audio_path}")
        
        audio_data, sr = librosa.load(request.audio_path, sr=16000, mono=True)
        
        # 2. Extract features
        # Mel-spectrogram
        melspec = librosa.feature.melspectrogram(y=audio_data, sr=sr, n_mels=128)
        melspec_db = librosa.power_to_db(melspec, ref=np.max)
        
        # MFCC
        mfcc = librosa.feature.mfcc(y=audio_data, sr=sr, n_mfcc=13)
        
        # 3. Run model
        human_score = model.predict(melspec_db, mfcc)  # 0-1
        
        # 4. Convert to 0-100 scale
        score_0_100 = human_score * 100
        
        # 5. Make verdict
        if score_0_100 >= 70:
            verdict = "human"
            confidence = min(100, score_0_100)
        elif score_0_100 <= 30:
            verdict = "synthetic"
            confidence = min(100, 100 - score_0_100)
        else:
            verdict = "uncertain"
            confidence = 50
        
        inference_time = (time.time() - start_time) * 1000
        
        logger.info(f"prediction: {verdict}, score={score_0_100:.1f}, time={inference_time:.1f}ms")
        
        return PredictResponse(
            score=int(score_0_100),
            confidence=int(confidence),
            verdict=verdict,
            inference_time_ms=round(inference_time, 2)
        )
    
    except Exception as e:
        logger.error(f"prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)