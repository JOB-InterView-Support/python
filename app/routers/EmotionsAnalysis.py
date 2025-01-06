from fastapi import FastAPI, File, UploadFile, APIRouter
from deepface import DeepFace
import mediapipe as mp
import cv2
import os
import time

router = APIRouter()

# 영상 저장 디렉토리
UPLOAD_DIRECTORY = r"D:\ik\study\프로젝트\JOBIS\test\video"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)


@router.get("/video")
def analyze_emotion():
    """카메라 연결(test용) 및 deepface 감정 분석"""
    cap = cv2.VideoCapture(0)  # 카메라 연결
    if not cap.isOpened():
        return {"error": "Unable to access the webcam"}

    # 테스트 프레임 읽기
    ret, frame = cap.read()
    if not ret:
        return {"error": "Failed to capture image from webcam"}

    cap.release()
    return {"message": "Camera connected successfully"}


@router.post("/video")
def record_video_endpoint(duration: int = 5):
    """웹캠에서 실시간으로 일정 시간 동안 영상을 녹화"""
    video_path = os.path.join(UPLOAD_DIRECTORY, f"recorded_{int(time.time())}.mp4")
    cap = cv2.VideoCapture(0)  # 웹캠 연결
    if not cap.isOpened():
        return {"error": "Unable to access the webcam"}

    # 비디오 저장 설정
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_path, fourcc, 20.0, (640, 480))

    start_time = time.time()
    while time.time() - start_time < duration:
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)  # 프레임 저장
    out.release()

    return {"message": "Recording completed", "video_path": video_path}

@router.get("/videolist")
def list_videos():
    """저장된 test 영상 목록 반환"""
    try:
        # 저장된 영상 파일 목록 가져오기
        videos = os.listdir(UPLOAD_DIRECTORY)
        return {"videos": videos}
    except Exception as e:
        # 오류 발생 시 반환
        return {"error": str(e)}

