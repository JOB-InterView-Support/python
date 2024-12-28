from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import cv2
import os
import time
from PIL import ImageFont, ImageDraw, Image
import numpy as np
from app.utils.db_connection import get_oracle_connection  # DB 연결 모듈 import

router = APIRouter()

# 전역 변수: DB 저장 상태 (기본값 False)
db_save_status = False

# Haar Cascade 파일 경로
cascade_path = os.path.join(os.path.dirname(__file__), "../models/haarcascade_frontalface_default.xml")
face_cascade = cv2.CascadeClassifier(cascade_path)

# 윈도우 기본 폰트 경로 설정 (맑은 고딕)
font_path = "C:/Windows/Fonts/malgun.ttf"  # Windows 기본 폰트인 '맑은 고딕'
font = ImageFont.truetype(font_path, 24)  # 폰트 크기 설정

# 얼굴 저장 폴더
save_folder = "C:/JOBISIMG/FACEID"
os.makedirs(save_folder, exist_ok=True)  # 폴더가 없으면 생성


def is_near_center(red_box, blue_box):
    """
    빨간 네모와 파란 네모가 근접했는지 판단
    """
    (red_x, red_y, red_w, red_h) = red_box
    (blue_x, blue_y, blue_w, blue_h) = blue_box

    # 중심 좌표 계산
    red_center = (red_x + red_w // 2, red_y + red_h // 2)
    blue_center = (blue_x + blue_w // 2, blue_y + blue_h // 2)

    # 중심 좌표 근접 여부
    center_distance = np.linalg.norm(np.array(red_center) - np.array(blue_center))

    # 크기 비교 (높이와 너비가 유사해야 함)
    size_diff = abs(red_w - blue_w) + abs(red_h - blue_h)

    # 근접 기준: 중심 좌표 거리와 크기 차이
    return center_distance < 25 and size_diff < 25  # 기준을 25로 수정


def update_or_insert_faceid(uuid, file_path):
    """
    USERS와 FACEID 테이블을 업데이트 또는 삽입
    """
    global db_save_status  # 전역 상태 변수

    conn = get_oracle_connection()
    if conn is None:
        print("DB 연결 실패")
        return

    try:
        cursor = conn.cursor()

        # USERS 테이블에서 USER_FACEID_STATUS 업데이트
        update_users_query = """
            UPDATE USERS
            SET USER_FACEID_STATUS = 'Y'
            WHERE UUID = :uuid
        """
        cursor.execute(update_users_query, {"uuid": uuid})

        # FACEID 테이블에서 데이터 존재 여부 확인
        check_faceid_query = """
            SELECT COUNT(*)
            FROM FACEID
            WHERE UUID = :uuid
        """
        cursor.execute(check_faceid_query, {"uuid": uuid})
        faceid_exists = cursor.fetchone()[0] > 0

        if faceid_exists:
            # 데이터가 존재하면 업데이트
            update_faceid_query = """
                UPDATE FACEID
                SET IMAGE_PATH = :image_path,
                    UPDATE_AT = SYSDATE
                WHERE UUID = :uuid
            """
            cursor.execute(update_faceid_query, {"image_path": file_path, "uuid": uuid})
        else:
            # 데이터가 없으면 삽입
            insert_faceid_query = """
                INSERT INTO FACEID (USER_FACE_ID, UUID, IMAGE_PATH, CAPTURED_AT, UPDATE_AT)
                VALUES (:user_face_id, :uuid, :image_path, SYSDATE, SYSDATE)
            """
            user_face_id = f"{uuid}FACEID"
            cursor.execute(insert_faceid_query, {
                "user_face_id": user_face_id,
                "uuid": uuid,
                "image_path": file_path
            })

        conn.commit()
        print("DB 작업 완료")

        # DB 저장 상태를 True로 변경
        db_save_status = True
    except Exception as e:
        print(f"DB 작업 중 오류 발생: {e}")
        conn.rollback()
        db_save_status = False  # 오류 발생 시 상태 초기화
    finally:
        cursor.close()
        conn.close()


def generate_video_stream(uuid):
    """
    실시간 카메라 스트림 생성 함수
    """
    global db_save_status  # 전역 상태 변수

    cap = cv2.VideoCapture(0)  # 0번 카메라 사용
    if not cap.isOpened():
        raise RuntimeError("카메라를 열 수 없습니다.")

    count_down = 0  # 카운트다운 초기값
    last_count_time = time.time()  # 마지막 카운트 업데이트 시간

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 원본 프레임 복사 (저장용)
            original_frame = frame.copy()

            # 좌우 반전
            frame = cv2.flip(frame, 1)

            # 중앙 빨간 네모
            height, width, _ = frame.shape
            center_x, center_y = width // 2, height // 2
            red_box = (center_x - 140, center_y - 140, 280, 280)  # 빨간 네모
            top_left = (red_box[0], red_box[1])
            bottom_right = (red_box[0] + red_box[2], red_box[1] + red_box[3])

            # 얼굴 감지
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

            # 얼굴 네모 표시 (파란색)
            for (x, y, w, h) in faces:
                blue_box = (x, y, w, h)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)  # 파란색 네모

                # 빨간 네모와 파란 네모가 근접하면 초록색으로 변경
                if is_near_center(red_box, blue_box):
                    cv2.rectangle(frame, top_left, bottom_right, (0, 255, 0), 2)  # 초록색 네모
                    if count_down == 0:
                        count_down = 3  # 카운트다운 시작
                    break
            else:
                # 근접하지 않으면 빨간 네모 유지
                cv2.rectangle(frame, top_left, bottom_right, (0, 0, 255), 2)

            # 메시지와 카운트다운 표시
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame)
            draw = ImageDraw.Draw(pil_img)

            if count_down > 0:
                current_time = time.time()
                if current_time - last_count_time >= 1:  # 1초 간격으로 카운트 감소
                    count_down -= 1
                    last_count_time = current_time

                message = f"얼굴을 유지해주세요 {count_down}"
                if count_down == 0:
                    # 얼굴 저장 (원본 프레임 저장)
                    timestamp = int(time.time())
                    file_name = f"{save_folder}/{uuid}FACEID{timestamp}.jpg"
                    cv2.imwrite(file_name, original_frame)  # 원본 프레임 저장

                    # DB 업데이트 또는 삽입
                    update_or_insert_faceid(uuid, file_name)

                    # 카메라 종료 및 스트리밍 중단
                    cap.release()  # 카메라 릴리즈
                    db_save_status = True  # DB 저장 완료 상태 업데이트
                    raise StopIteration  # 스트리밍 종료
            else:
                message = "얼굴을 중앙에 맞춰주세요"

            text_width, text_height = draw.textbbox((0, 0), message, font=font)[2:]
            text_position = ((width - text_width) // 2, 10)
            draw.text(text_position, message, font=font, fill=(255, 255, 255))

            frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

            # 프레임을 JPG로 인코딩
            _, buffer = cv2.imencode(".jpg", frame)
            frame_bytes = buffer.tobytes()

            yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
    except StopIteration:
        print("스트리밍이 종료되었습니다.")
    finally:
        cap.release()


@router.get("/streamVideo")
def stream_video(uuid: str):
    """
    실시간 카메라 스트림을 반환합니다.
    """
    return StreamingResponse(
        generate_video_stream(uuid),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/streamVideo")
def stream_video(uuid: str):
    """
    실시간 카메라 스트림을 반환합니다.
    """
    return StreamingResponse(
        generate_video_stream(uuid),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/checkSaveStatus")
def check_save_status():
    """
    DB 저장 상태를 반환하고 초기화합니다.
    """
    global db_save_status  # 전역 변수 사용
    current_status = db_save_status  # 현재 상태를 임시로 저장
    db_save_status = False  # 상태를 초기화
    return {"db_save_status": current_status}

