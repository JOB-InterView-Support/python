from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routers import FaceRegistration, FaceImage, FaceLogin

# FastAPI 인스턴스 생성
app = FastAPI()

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React 개발 서버
        "http://localhost:8080",  # 다른 서버 주소
    ],
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

# 라우터 등록
app.include_router(FaceRegistration.router, prefix="/faceRegistration", tags=["Face Registration"])
app.include_router(FaceImage.router, prefix="/faceId", tags=["Face ID"])  # 새로운 라우터 등록
app.include_router(FaceLogin.router, prefix="/faceLogin", tags=["Face Login"])  # 새로운 라우터 등록


@app.get("/")
def read_root():
    return {"message": "Welcome to the JOBIS FastAPI!"}


# FastAPI 실행
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
