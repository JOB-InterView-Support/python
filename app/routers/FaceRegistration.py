from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, JSONResponse
import cv2
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import math
import time
from datetime import datetime

# db_connection에서 update_faceid_status 함수 임포트
from app.utils.db_connection import update_faceid_status

router = APIRouter()

# Haar Cascade 파일 경로
HAAR_CASCADE_PATH = os.path.join(os.path.dirname(__file__), "../models/haarcascade_frontalface_default.xml")

# 얼굴 이미지 저장 경로
IMAGE_SAVE_DIR = "C:/JOBISIMG/FACEID"

# 얼굴 감지 및 스트리밍 함수
def generate_video_frames(uuid: str):
    # Haar Cascade 로드
    face_cascade = cv2.CascadeClassifier(HAAR_CASCADE_PATH)
    if face_cascade.empty():
        raise RuntimeError(f"Haar Cascade 파일을 로드할 수 없습니다: {HAAR_CASCADE_PATH}")

    # 카메라 열기
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("카메라를 열 수 없습니다.")

    is_centered = False
    countdown_start_time = None
    countdown_value = 3
    is_image_saved = False

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 원본 프레임을 복사 (네모가 없는 이미지 저장용)
        original_frame = frame.copy()

        # 프레임 좌우 반전
        flipped_frame = cv2.flip(frame, 1)

        # 프레임의 크기 가져오기
        height, width, _ = flipped_frame.shape

        # 중앙의 빨간 네모 정의
        box_size = 280
        x_start = (width - box_size) // 2
        y_start = (height - box_size) // 2
        x_end = x_start + box_size
        y_end = y_start + box_size

        # 빨간 네모의 중심점 계산
        red_center_x = (x_start + x_end) // 2
        red_center_y = (y_start + y_end) // 2

        # 그레이스케일로 변환 (얼굴 감지를 위해)
        gray_frame = cv2.cvtColor(flipped_frame, cv2.COLOR_BGR2GRAY)

        # 얼굴 감지
        faces = face_cascade.detectMultiScale(
            gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )

        is_close = False  # 얼굴이 중앙에 맞는지 확인

        # 감지된 얼굴에 파란색 사각형 그리기
        for (x, y, w, h) in faces:
            # 파란 네모의 중심점 계산
            blue_center_x = x + w // 2
            blue_center_y = y + h // 2

            # 중심점 거리 계산
            center_distance = math.sqrt(
                (red_center_x - blue_center_x) ** 2 + (red_center_y - blue_center_y) ** 2
            )

            # 빨간 네모와 파란 네모의 변 근접 여부 확인
            x_close = abs(x_start - x) < 30 or abs(x_end - (x + w)) < 30
            y_close = abs(y_start - y) < 30 or abs(y_end - (y + h)) < 30

            # 중심점과 네 변 모두 근접하면 초록색으로 변경
            if center_distance < 30 and x_close and y_close:
                is_close = True

        # 메시지와 네모 색상 처리
        if is_close:
            if not is_centered:
                is_centered = True
                countdown_start_time = time.time()  # 카운트다운 시작
                countdown_value = 3
            else:
                elapsed_time = time.time() - countdown_start_time
                if elapsed_time >= 1:  # 1초마다 카운트다운 감소
                    countdown_value -= 1
                    countdown_start_time = time.time()

                if countdown_value <= 0 and not is_image_saved:
                    countdown_message = "완료되었습니다!"
                    color = (0, 255, 0)  # 초록색

                    # 얼굴 이미지 저장
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    file_name = f"{uuid}_FACEID_{timestamp}.jpg"

                    # 폴더 생성
                    os.makedirs(IMAGE_SAVE_DIR, exist_ok=True)

                    # 네모 없는 원본 이미지를 저장
                    save_path = os.path.join(IMAGE_SAVE_DIR, file_name)
                    cv2.imwrite(save_path, original_frame)

                    print(f"이미지가 저장되었습니다: {save_path}")

                    # Oracle DB에 USER_FACEID_STATUS를 'Y'로 업데이트
                    update_faceid_status(uuid)

                    is_image_saved = True  # 저장 상태 업데이트


                else:
                    countdown_message = f"{countdown_value}"
                    color = (0, 255, 0)  # 초록색
        else:
            is_centered = False
            is_image_saved = False  # 다시 저장 가능하도록 상태 초기화
            countdown_message = "중앙에 얼굴을 맞춰주세요"
            color = (0, 0, 255)  # 빨간 네모

        # 얼굴 감지 네모는 파란색으로 표시
        for (x, y, w, h) in faces:
            cv2.rectangle(flipped_frame, (x, y), (x + w, y + h), (255, 0, 0), 2)  # 파란색 네모

        # 중앙 네모는 빨간색 또는 초록색으로 표시
        cv2.rectangle(flipped_frame, (x_start, y_start), (x_end, y_end), color, 2)

        # 한글 메시지 추가 (Pillow로 생성 후 OpenCV로 변환)
        font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 32)
        pil_img = Image.fromarray(cv2.cvtColor(flipped_frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)

        # 메시지 출력
        text_bbox = draw.textbbox((0, 0), countdown_message, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        text_x = (width - text_width) // 2
        text_y = 50  # 메시지를 화면 상단에 표시
        draw.text((text_x, text_y), countdown_message, font=font, fill=(255, 255, 255))
        flipped_frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        # 프레임을 JPEG로 인코딩
        _, buffer = cv2.imencode(".jpg", flipped_frame)
        frame_bytes = buffer.tobytes()

        # HTTP 스트림 포맷으로 반환
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")

    cap.release()


@router.get("/stream-video")
def stream_video(uuid: str = Query(...)):
    if not uuid:
        return {"error": "UUID가 제공되지 않았습니다."}

    print(f"Received UUID: {uuid}")  # UUID를 로그에 출력

    # 얼굴 감지 스트리밍 시작
    return StreamingResponse(generate_video_frames(uuid), media_type="multipart/x-mixed-replace; boundary=frame")
