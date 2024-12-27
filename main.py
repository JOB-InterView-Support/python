from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import face  # 새로 추가된 라우터 임포트

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
app.include_router(face.router)  # face.py 라우터 추가

@app.get("/")
def read_root():
    return {"message": "Welcome to the JOBIS FastAPI!"}
