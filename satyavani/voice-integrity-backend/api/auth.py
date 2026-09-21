from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os

SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)
    
    @staticmethod
    def create_token(user_id: int, org_id: int) -> str:
        payload = {
            "user_id": user_id,
            "org_id": org_id,
            "exp": datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    @staticmethod
    def verify_token(token: str) -> dict:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            raise ValueError("Invalid token")

from fastapi.security import HTTPBearer, HTTPAuthCredentials
from fastapi import Depends, HTTPException

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthCredentials = Depends(security)):
    try:
        payload = AuthService.verify_token(credentials.credentials)
        user_id = payload.get("user_id")
        org_id = payload.get("org_id")
        if not user_id or not org_id:
            raise ValueError("Invalid token payload")
        return {"user_id": user_id, "org_id": org_id}
    except:
        raise HTTPException(status_code=401, detail="Invalid or expired token")