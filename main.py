from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routers import FaceRegistration, FaceImage, FaceLogin, AddQuestionNAnswer

# FastAPI 인스턴스 생성
app = FastAPI()

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080", "http://127.0.0.1:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# 라우터 등록
app.include_router(FaceRegistration.router, prefix="/faceRegistration", tags=["Face Registration"])
app.include_router(FaceImage.router, prefix="/faceId", tags=["Face ID"])  # 새로운 라우터 등록
app.include_router(FaceLogin.router, prefix="/faceLogin", tags=["Face Login"])  # 새로운 라우터 등록
app.include_router(AddQuestionNAnswer.router, prefix="/interview", tags=["Interview Questions"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the JOBIS FastAPI!"}


# FastAPI 실행
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
