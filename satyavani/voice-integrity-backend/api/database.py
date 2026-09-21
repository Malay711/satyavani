from sqlalchemy.orm import declarative_base, Session
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, BigInteger, ForeignKey, LargeBinary, JSON, INET
from datetime import datetime

Base = declarative_base()

class Organization(Base):
    __tablename__ = "organizations"
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)
    api_key = Column(String(255), unique=True)
    tier = Column(String(32), default="free")
    quota_monthly = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    org_id = Column(BigInteger, ForeignKey("organizations.id"))
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    
    audio_file_path = Column(String(512))
    audio_file_hash = Column(String(64))
    audio_duration_ms = Column(Integer)
    sample_rate = Column(Integer, default=16000)
    file_size_bytes = Column(Integer)
    
    source = Column(String(32), default="upload")
    user_note = Column(Text)
    
    status = Column(String(32), default="queued")
    error_message = Column(Text)
    
    processing_started_at = Column(DateTime)
    processing_ended_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)

class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id = Column(BigInteger, primary_key=True)
    job_id = Column(BigInteger, ForeignKey("analysis_jobs.id"), unique=True, nullable=False)
    
    verdict = Column(String(32))
    authenticity_score = Column(Integer)
    risk_score = Column(Integer)
    confidence = Column(Integer)
    
    anti_spoof_score = Column(Integer)
    temporal_consistency = Column(Integer)
    spectral_score = Column(Integer)
    replay_indicator = Column(Integer)
    
    model_version = Column(String(64), default="aasist-v1.0")
    inference_time_ms = Column(Integer)
    
    feature_data = Column(JSON)
    risk_timeline = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)

class EvidenceRecord(Base):
    __tablename__ = "evidence_records"
    id = Column(BigInteger, primary_key=True)
    result_id = Column(BigInteger, ForeignKey("analysis_results.id"), nullable=False)
    
    evidence_type = Column(String(64))
    label = Column(String(255))
    score = Column(Integer)
    interpretation = Column(String(32))
    details = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(BigInteger, primary_key=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"))
    user_id = Column(BigInteger, ForeignKey("users.id"))
    
    action = Column(String(64))
    resource_type = Column(String(64))
    resource_id = Column(BigInteger)
    
    ip_address = Column(INET)
    status_code = Column(Integer)
    error_message = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db(engine):
    Base.metadata.create_all(bind=engine)