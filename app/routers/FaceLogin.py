from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
import cv2
import os
import time
from deepface import DeepFace  # DeepFace 사용

router = APIRouter()

# 전역 변수 정의
uuidStatus = False
countdown = 3  # 카운트다운 초기값
last_update_time = time.time()  # 마지막 카운트다운 업데이트 시간
image_saved = False  # 이미지 캡처 상태

# 사진 비교에 사용할 폴더 경로
compare_folder = "C:/JOBISIMG/FACEID"

# Haarcascade 파일 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
haarcascade_path = os.path.join(current_dir, "../models/haarcascade_frontalface_default.xml")

# 얼굴 탐지기 초기화
face_cascade = cv2.CascadeClassifier(haarcascade_path)


# OpenCV에서 한글을 지원하기 위해 Windows 기본 폰트 설정
def put_korean_text(img, text, position, font_size, color):
    """이미지에 한글 텍스트 추가."""
    import numpy as np
    from PIL import ImageFont, ImageDraw, Image

    # 윈도우 기본 폰트 경로 설정
    font_path = "C:/Windows/Fonts/malgun.ttf"
    font = ImageFont.truetype(font_path, font_size)

    # OpenCV 이미지를 PIL 이미지로 변환
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)

    # 텍스트 크기 계산 (textbbox 사용)
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]

    # 위치를 동적으로 조정 (좌우 가운데 정렬)
    adjusted_position = (position[0] - text_width // 2, position[1])

    # 텍스트 추가
    draw.text(adjusted_position, text, font=font, fill=color)

    # PIL 이미지를 다시 OpenCV 이미지로 변환
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def is_near(face_coords, center_coords, tolerance):
    """얼굴과 빨간 네모의 중앙 및 네 변이 근접한지 확인."""
    fx, fy, fw, fh = face_coords
    cx, cy, box_size = center_coords
    half_size = box_size // 2

    # 빨간 네모의 중앙 좌표와 상하좌우 경계
    red_center_x, red_center_y = cx, cy
    red_top, red_bottom = cy - half_size, cy + half_size
    red_left, red_right = cx - half_size, cx + half_size

    # 얼굴의 중앙 좌표와 상하좌우 경계
    face_center_x, face_center_y = fx + fw // 2, fy + fh // 2
    face_top, face_bottom = fy, fy + fh
    face_left, face_right = fx, fx + fw

    # 근접 여부 계산
    return (
            abs(face_center_x - red_center_x) <= tolerance and
            abs(face_center_y - red_center_y) <= tolerance and
            abs(face_top - red_top) <= tolerance and
            abs(face_bottom - red_bottom) <= tolerance and
            abs(face_left - red_left) <= tolerance and
            abs(face_right - red_right) <= tolerance
    )


def compare_images(captured_image_path):
    """캡처된 이미지와 폴더 내 이미지들을 비교."""
    global compare_folder
    matching_files = []
    for file_name in os.listdir(compare_folder):
        file_path = os.path.join(compare_folder, file_name)
        if os.path.isfile(file_path):
            try:
                # DeepFace를 사용하여 이미지 비교
                result = DeepFace.verify(captured_image_path, file_path, model_name="VGG-Face", enforce_detection=False)
                score = result['similarity'] * 100  # 유사도를 백분율로 변환
                if score >= 70:  # 90점 이상 일치
                    matching_files.append(file_name)
            except Exception as e:
                print(f"비교 실패: {file_name}, 오류: {e}")
    return matching_files


def generate_frames():
    """카메라 스트림을 생성하는 제너레이터 함수."""
    global countdown, last_update_time, image_saved
    cap = cv2.VideoCapture(0)  # 카메라 열기
    if not cap.isOpened():
        raise RuntimeError("카메라를 열 수 없습니다.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 좌우 반전
        frame = cv2.flip(frame, 1)

        # 얼굴 감지
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        # 화면 중앙에 빨간 네모 그리기
        height, width, _ = frame.shape
        center_x, center_y = width // 2, height // 2
        box_size = 280
        top_left = (center_x - box_size // 2, center_y - box_size // 2)
        bottom_right = (center_x + box_size // 2, center_y + box_size // 2)

        # 초기 메시지
        message = "얼굴을 중앙에 맞춰주세요"
        box_color = (0, 0, 255)  # 빨간색

        face_near_center = False

        for (x, y, w, h) in faces:
            # 얼굴 감지 네모
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)  # 파란색 네모

            if is_near((x, y, w, h), (center_x, center_y, box_size), 25):
                face_near_center = True
                break

        if face_near_center:
            # 초록색 네모 및 메시지 변경
            box_color = (0, 255, 0)  # 초록색
            current_time = time.time()

            # 1초마다 카운트다운 감소
            if current_time - last_update_time >= 1:
                countdown -= 1
                last_update_time = current_time

            if countdown > 0:
                message = f"얼굴을 유지해주세요 {countdown}"
            else:
                message = "캡처 완료!"
                if not image_saved:
                    # 캡처 및 비교
                    captured_image_path = "captured_image.jpg"
                    cv2.imwrite(captured_image_path, frame)  # 원본 이미지 저장
                    matching_files = compare_images(captured_image_path)
                    if matching_files:
                        print("일치하는 파일명:", matching_files)
                    else:
                        print("일치하는 파일 없음")
                    image_saved = True
        else:
            # 얼굴이 벗어나면 카운트다운 초기화
            countdown = 3
            message = "얼굴을 중앙에 맞춰주세요"
            image_saved = False

        # 네모 그리기
        cv2.rectangle(frame, top_left, bottom_right, box_color, 2)

        # 메시지 추가
        frame = put_korean_text(frame, message, (center_x, 50), 30, (255, 255, 255))  # 흰색 텍스트

        # 프레임을 JPEG로 인코딩
        _, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        # 스트리밍 응답에 필요한 형식으로 프레임 반환
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()


@router.get("/stream")
def video_stream():
    """카메라 스트림을 클라이언트로 스트리밍."""
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/uuidStatus")
def get_uuid_status():
    """uuidStatus 값을 반환."""
    global uuidStatus
    return JSONResponse(content={"uuidStatus": uuidStatus})
