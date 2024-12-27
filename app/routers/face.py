from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
import cv2
import os
import time
from pathlib import Path
import numpy as np  # np 에러 해결
from app.utils.text_util import draw_text_korean  # 한글 텍스트 유틸리티 함수

# APIRouter 설정
router = APIRouter(prefix="/face", tags=["Face Registration"])

# Haar Cascade 경로 설정
HAAR_CASCADE_PATH = "app/models/haarcascade_frontalface_default.xml"
if not os.path.exists(HAAR_CASCADE_PATH):
    raise FileNotFoundError(f"Haar Cascade 파일을 찾을 수 없습니다: {HAAR_CASCADE_PATH}")

# 이미지 저장 경로 설정
SAVE_DIRECTORY = r"C:\JOBISIMG\FaceLogin"

# 저장 디렉토리 생성 함수
def ensure_save_directory():
    """이미지 저장 경로가 없으면 생성"""
    if not os.path.exists(SAVE_DIRECTORY):
        os.makedirs(SAVE_DIRECTORY)

# 스트리밍 함수
def generate_camera_stream(uuid: str):
    """카메라 스트리밍 및 얼굴 감지"""
    cap = cv2.VideoCapture(0)
    face_cascade = cv2.CascadeClassifier(HAAR_CASCADE_PATH)

    countdown_active = False
    countdown_frames = 90  # 3초 (30 FPS 기준)
    last_captured = False

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 좌우 반전
        frame = cv2.flip(frame, 1)
        original_frame = frame.copy()

        # 화면 크기
        height, width, _ = frame.shape
        center_x, center_y = width // 2, height // 2
        box_size = 280

        # 중앙 네모 위치
        box_x1, box_y1 = center_x - box_size // 2, center_y - box_size // 2
        box_x2, box_y2 = center_x + box_size // 2, center_y + box_size // 2

        # 얼굴 탐지
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100)
        )

        # 기본 메시지
        message = "화면 중앙에 얼굴을 맞춰주세요!"
        box_color = (0, 0, 255)  # 빨간색

        for (x, y, w, h) in faces:
            face_center_x = x + w // 2
            face_center_y = y + h // 2
            distance = ((face_center_x - center_x) ** 2 + (face_center_y - center_y) ** 2) ** 0.5

            # 얼굴이 중앙 박스에 가까운 경우
            if (
                abs(face_center_x - center_x) < 50
                and abs(face_center_y - center_y) < 50
                and abs(w - box_size) / box_size < 0.2
                and abs(h - box_size) / box_size < 0.2
            ):
                box_color = (0, 255, 0)  # 초록색
                if not countdown_active:
                    countdown_active = True
                    countdown_frames = 90

                if countdown_frames > 0:
                    message = f"얼굴을 유지해주세요! {countdown_frames // 30}"
                    countdown_frames -= 1
                else:
                    if not last_captured:
                        ensure_save_directory()
                        timestamp = int(time.time())
                        file_name = f"{uuid}_FACE_{timestamp}.jpg"
                        file_path = os.path.join(SAVE_DIRECTORY, file_name)
                        cv2.imwrite(file_path, original_frame)
                        last_captured = True
                        cap.release()
                        return  # 스트리밍 종료
            else:
                countdown_active = False
                countdown_frames = 90

            # 얼굴에 네모 그리기
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

        # 중앙 박스 그리기
        cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), box_color, 3)

        # 메시지 표시
        frame = draw_text_korean(frame, message, (50, 50), font_size=100, color=(0, 255, 255))

        # 프레임을 JPEG로 변환
        _, buffer = cv2.imencode(".jpg", frame)
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")

# 엔드포인트: 얼굴 등록 스트리밍
@router.get("/register")
async def face_register(uuid: str = Query(...)):
    """얼굴 등록 스트리밍 엔드포인트"""
    if not uuid:
        raise HTTPException(status_code=400, detail="UUID가 필요합니다.")
    return StreamingResponse(
        generate_camera_stream(uuid),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
