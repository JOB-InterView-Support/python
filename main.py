from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
import cv2
from app.routers import FaceRegistration, FaceImage, FaceLogin, AddQuestionNAnswer, AiInterview, AddSelfIntroduce, Voice, VideoPosition, InterviewSave, VideoAnalyze, AudioAnalyze

# FastAPI 인스턴스 생성
app = FastAPI()

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080", "http://127.0.0.1:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# 라우터 등록
app.include_router(FaceRegistration.router, prefix="/faceRegistration", tags=["Face Registration"])
app.include_router(FaceImage.router, prefix="/faceId", tags=["Face ID"])
app.include_router(FaceLogin.router, prefix="/faceLogin", tags=["Face Login"])
app.include_router(AddQuestionNAnswer.router, prefix="/interview", tags=["Interview Questions"])
app.include_router(AiInterview.router, prefix="/aiInterview", tags=["AI Interview"])  # AiInterview 라우터 추가
app.include_router(AddSelfIntroduce.router, prefix="/addSelfIntroduce", tags=["Add Self Introduce"])
app.include_router(Voice.router, prefix="/voice", tags=["Voice"])
app.include_router(VideoPosition.router, prefix="/videoPosition", tags=["VideoPosition"])
app.include_router(InterviewSave.router, prefix="/interviewSave", tags=["interviewSave"])
app.include_router(VideoAnalyze.router, prefix="/videoAnalyze", tags=["videoAnalyze"])
app.include_router(AudioAnalyze.router, prefix="/audioAnalyze", tags=["audioAnalyze"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the JOBIS FastAPI!"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
