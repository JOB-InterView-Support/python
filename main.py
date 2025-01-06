from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
import cv2
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

# 카메라 스트림 열기
camera = cv2.VideoCapture(0)  # 0은 기본 카메라를 의미

def generate_frames():
    while True:
        success, frame = camera.read()  # 카메라에서 프레임 읽기
        if not success:
            break

        # 좌우 반전 처리
        flipped_frame = cv2.flip(frame, 1)  # 1은 좌우 반전, 0은 상하 반전

        # 프레임을 JPEG 형식으로 인코딩
        _, buffer = cv2.imencode(".jpg", flipped_frame)
        frame_bytes = buffer.tobytes()

        # HTTP 스트리밍 응답에 프레임 전달
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )

@app.get("/video_feed")
def video_feed():
    """카메라 스트리밍 엔드포인트"""
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

@app.get("/")
def read_root():
    return {"message": "Welcome to the JOBIS FastAPI!"}




# FastAPI 실행
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
