from fastapi import FastAPI, APIRouter, HTTPException
from datetime import datetime
import time
import mediapipe as mp
import cv2
import os
import numpy as np

# FastAPI 및 라우터 초기화
app = FastAPI(docs_url="/docs", redoc_url="/redoc")
router = APIRouter()

# 디렉토리 설정
BASE_DIRECTORY = r"D:\ik\study\프로젝트\JOBIS\videosave_test"
GAZE_ANALYSIS_DIRECTORY = r"D:\ik\study\프로젝트\JOBIS\analysis_test"

# Mediapipe 초기화
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=True)

# 함수 정의
def calculate_gaze_vector(eye_landmarks):
    """눈 랜드마크를 기반으로 시선 벡터 계산"""
    eye_center = np.mean(eye_landmarks, axis=0)
    eye_outer = eye_landmarks[0]  # 눈의 가장 바깥쪽
    gaze_vector = np.array(eye_outer) - np.array(eye_center)
    return gaze_vector

def is_looking_off_screen(eye_center, frame_width, threshold=50):
    """눈의 중심이 화면 좌우 경계를 벗어났는지 확인"""
    x, _ = eye_center
    return x < threshold or x > frame_width - threshold

@router.post("/record")
def record_video():
    """
    실시간 원본 비디오 저장 및 웹캠 화면 출력
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_id = f"recordtest_{timestamp}"
    video_path = os.path.join(BASE_DIRECTORY, f"{video_id}.mp4")

    # 웹캠 열기
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Unable to access webcam for recording.")

    # 비디오 저장 설정
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_path, fourcc, 20.0, (frame_width, frame_height))

    start_time = datetime.now()
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 웹캠 화면 출력
        cv2.imshow("Webcam Recording", frame)

        # 비디오 저장
        out.write(frame)

        # 종료 조건: 20초 경과 또는 'q' 키 입력
        elapsed_time = (datetime.now() - start_time).total_seconds()
        if elapsed_time >= 20 or (cv2.waitKey(1) & 0xFF == ord('q')):
            break

    # 리소스 해제
    cap.release()
    out.release()
    cv2.destroyAllWindows()

    return {"message": "Video recorded successfully.", "video_id": video_id, "video_path": video_path}

@router.get("/list")
def list_videos():
    """
    저장된 원본 비디오 목록 조회
    """
    if not os.path.exists(BASE_DIRECTORY):
        return {"message": "No videos found.", "videos": []}

    # mp4 파일 필터링 및 목록 생성
    video_files = [
        f for f in os.listdir(BASE_DIRECTORY)
        if os.path.isfile(os.path.join(BASE_DIRECTORY, f)) and f.endswith(".mp4")
    ]

    return {"message": "Video list retrieved successfully.", "videos": video_files}

@router.post("/analyze")
def analyze_video(video_id: str):
    """
    비디오 분석 및 시각화 저장
    """
    os.makedirs(BASE_DIRECTORY, exist_ok=True)
    os.makedirs(GAZE_ANALYSIS_DIRECTORY, exist_ok=True)

    video_path = os.path.join(BASE_DIRECTORY, f"{video_id}.mp4")
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found.")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Unable to open video for analysis.")

    # 분석 결과 비디오 저장 설정
    analyzed_video_path = os.path.join(
        GAZE_ANALYSIS_DIRECTORY, f"{video_id.replace('recordtest_', '')}_gaze_analyzed.mp4"
    )
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(analyzed_video_path, fourcc, fps, (frame_width, frame_height))

    # Mediapipe 시각화 초기화
    prev_left_eye, prev_right_eye = None, None
    eye_movement_list = []
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(frame_rgb)

        eye_movement = 0  # 이동률 초기화
        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                # 왼쪽 눈과 오른쪽 눈의 랜드마크
                left_eye_landmarks = [face_landmarks.landmark[i] for i in range(133, 144)]
                right_eye_landmarks = [face_landmarks.landmark[i] for i in range(362, 373)]

                left_eye_coords = [
                    (int(lm.x * frame_width), int(lm.y * frame_height)) for lm in left_eye_landmarks
                ]
                right_eye_coords = [
                    (int(lm.x * frame_width), int(lm.y * frame_height)) for lm in right_eye_landmarks
                ]

                # 눈 중심 계산
                left_eye_center = np.mean(left_eye_coords, axis=0)
                right_eye_center = np.mean(right_eye_coords, axis=0)

                # 외부 시선 감지
                if is_looking_off_screen(left_eye_center, frame_width) or is_looking_off_screen(
                    right_eye_center, frame_width
                ):
                    cv2.putText(
                        frame,
                        "Looking Off Screen!",
                        (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 0, 255),
                        2,
                    )

                # 이동률 계산
                if prev_left_eye is not None and prev_right_eye is not None:
                    left_eye_diff = np.linalg.norm(
                        np.array(left_eye_coords) - np.array(prev_left_eye)
                    )
                    right_eye_diff = np.linalg.norm(
                        np.array(right_eye_coords) - np.array(prev_right_eye)
                    )
                    eye_movement = (left_eye_diff + right_eye_diff) / 2
                    eye_movement_list.append(eye_movement)

                prev_left_eye = left_eye_coords
                prev_right_eye = right_eye_coords

                # 랜드마크 시각화
                for (x, y) in left_eye_coords + right_eye_coords:
                    cv2.circle(frame, (x, y), 2, (0, 255, 0), -1)

        # 화면에 시간과 이동률 출력
        elapsed_time = time.time() - start_time
        cv2.putText(
            frame,
            f"Time: {elapsed_time:.1f}s",
            (10, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 0),
            2,
        )
        cv2.putText(
            frame,
            f"Movement: {eye_movement:.2f}",
            (10, 130),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 0),
            2,
        )

        # 분석 결과 비디오에 저장
        out.write(frame)

    cap.release()
    out.release()

    # 이동률 통계 계산
    if eye_movement_list:
        avg_movement = np.mean(eye_movement_list)
        max_movement = np.max(eye_movement_list)
        min_movement = np.min(eye_movement_list)
        movement_variation = ((max_movement - min_movement) / avg_movement) * 100

        # 통계 결과 출력
        print(f"평균 이동률: {avg_movement:.2f}")
        print(f"최대 이동률: {max_movement:.2f}")
        print(f"최소 이동률: {min_movement:.2f}")
        print(f"변동률: {movement_variation:.2f}%")

    return {
        "message": "Video analyzed and saved successfully.",
        "analyzed_video_path": analyzed_video_path,
    }
