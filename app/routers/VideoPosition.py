from fastapi import FastAPI, APIRouter, HTTPException
from datetime import datetime
import cv2
import mediapipe as mp
import numpy as np
import os
from pydantic import BaseModel

app = FastAPI(docs_url="/docs", redoc_url="/redoc")
router = APIRouter()

BASE_DIRECTORY = r"D:\ik\study\프로젝트\JOBIS\videosave_test"
ANALYSIS_DIRECTORY = r"D:\ik\study\프로젝트\JOBIS\analysis_test"

# Mediapipe 초기화
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.8, min_tracking_confidence=0.8)

# 결과값 저장
ANALYSIS_RESULTS = {}

class VideoRequest(BaseModel):
    prefix: str  # Prefix for the video ID (e.g., 'test')

@router.post("/video/record/save")
def save_video():
    """
    실시간 영상 저장 기능
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_id = f"recordtest_{timestamp}"
    video_path = os.path.join(BASE_DIRECTORY, f"{video_id}.mp4")
    os.makedirs(BASE_DIRECTORY, exist_ok=True)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Unable to access webcam for recording.")

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_path, fourcc, 20.0, (frame_width, frame_height))

    start_time = datetime.now()
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        out.write(frame)
        cv2.imshow("Recording", frame)

        # 20초 제한 체크
        elapsed_time = (datetime.now() - start_time).total_seconds()
        if elapsed_time >= 20:
            break

        if cv2.waitKey(1) & 0xFF == 27:  # ESC로 종료
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()

    return {"message": "Video saved successfully.", "video_id": video_id, "video_path": video_path}


# @router.post("/video/record")
# def record_video(request: VideoRequest):
#     """
#     면접영상 촬영 후 저장 및 Mediapipe Pose 처리
#     """
#     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#     video_id = f"recordtest_{timestamp}"
#     video_path = os.path.join(BASE_DIRECTORY, f"{video_id}.mp4")
#     os.makedirs(BASE_DIRECTORY, exist_ok=True)
#
#     cap = cv2.VideoCapture(0)
#     if not cap.isOpened():
#         raise HTTPException(status_code=500, detail="Unable to access webcam for recording.")
#
#     frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#     frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#     fourcc = cv2.VideoWriter_fourcc(*"mp4v")
#     out = cv2.VideoWriter(video_path, fourcc, 20.0, (frame_width, frame_height))
#
#     start_time = datetime.now()
#     while True:
#         ret, frame = cap.read()
#         if not ret:
#             break
#
#         rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#         pose_results = pose.process(rgb_frame)
#
#         pose_status = "Pose not detected"
#         shoulder_angle = None
#         nose_to_shoulder_angle = None
#         shoulder_center_x = None
#         condition_1 = False
#         condition_2 = False
#
#         if pose_results.pose_landmarks:
#             landmarks = pose_results.pose_landmarks.landmark
#
#             # 양쪽 어깨 좌표
#             left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
#             right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
#
#             # 코 좌표
#             nose = landmarks[mp_pose.PoseLandmark.NOSE]
#             nose_position = (int(nose.x * frame_width), int(nose.y * frame_height))
#
#             # 어깨 좌표 변환 (픽셀 값)
#             left_shoulder_pos = (int(left_shoulder.x * frame_width), int(left_shoulder.y * frame_height))
#             right_shoulder_pos = (int(right_shoulder.x * frame_width), int(right_shoulder.y * frame_height))
#
#             # 어깨 중앙점 계산
#             shoulder_center_x = (left_shoulder.x + right_shoulder.x) / 2 * frame_width
#             shoulder_center_y = (left_shoulder.y + right_shoulder.y) / 2 * frame_height
#             shoulder_center_pos = (int(shoulder_center_x), int(shoulder_center_y))
#
#             # 어깨 중앙점의 화면 중앙과의 차이 확인
#             if abs(shoulder_center_x - (frame_width / 2)) <= 10:
#                 condition_2 = True
#
#             # 코와 어깨 중앙점 간의 각도 계산
#             nose_to_shoulder_angle = np.arctan2(
#                 nose.y * frame_height - shoulder_center_y,
#                 nose.x * frame_width - shoulder_center_x
#             ) * (180 / np.pi)
#
#             if 80 <= abs(nose_to_shoulder_angle) <= 100:
#                 condition_1 = True
#
#             # 자세 평가
#             if condition_1 and condition_2:
#                 pose_status = "Good pose"
#             elif not condition_1 and condition_2:
#                 pose_status = "Bad neck"
#             elif condition_1 and not condition_2:
#                 pose_status = "Bad shoulder"
#             else:
#                 pose_status = "Bad pose"
#
#             # 화면에 결과 표시
#             cv2.putText(frame, f"Pose: {pose_status}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
#             cv2.putText(frame, f"Nose-Shoulder Angle: {nose_to_shoulder_angle:.2f}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
#             cv2.putText(frame, f"Shoulder Center X: {shoulder_center_x:.2f}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
#
#             # 시각적 피드백
#             cv2.line(frame, left_shoulder_pos, right_shoulder_pos, (0, 255, 0), 2)  # 어깨 선
#             cv2.line(frame, nose_position, shoulder_center_pos, (255, 0, 0), 2)  # 코와 어깨 중앙 연결선
#
#         out.write(frame)
#         cv2.imshow("Recording", frame)
#
#         # 20초 제한 체크
#         elapsed_time = (datetime.now() - start_time).total_seconds()
#         if elapsed_time >= 20:
#             break
#
#         if cv2.waitKey(1) & 0xFF == 27:  # ESC로 종료
#             break
#
#     cap.release()
#     out.release()
#     cv2.destroyAllWindows()
#
#     return {"message": "Recording completed.", "video_id": video_id, "video_path": video_path}


@router.get("/video/list")
def list_videos():
    """
    저장된 면접영상 (원본) 목록 조회
    """
    if not os.path.exists(BASE_DIRECTORY):
        return {"message": "No videos found.", "videos": []}

    video_files = [
        f for f in os.listdir(BASE_DIRECTORY) if os.path.isfile(os.path.join(BASE_DIRECTORY, f)) and f.endswith(".mp4")
    ]

    return {"message": "Video list retrieved successfully.", "videos": video_files}



@router.post("/video/analyze")
def analyze_video(video_id: str):
    """
    저장된 면접영상 분석 및 평균값 추출
    """
    record_video_path = os.path.join(BASE_DIRECTORY, f"{video_id}.mp4")
    if not os.path.exists(record_video_path):
        raise HTTPException(status_code=404, detail="Video file not found.")

    cap = cv2.VideoCapture(record_video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Unable to open video for analysis.")

    # 새로운 저장용 비디오 초기화
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output_path = os.path.join(ANALYSIS_DIRECTORY, f"{video_id.replace('recordtest_', '')}_analyzed.mp4")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    total_frames = 0
    bad_pose_frames = 0
    bad_neck_frames = 0
    bad_shoulder_frames = 0
    good_pose_frames = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        total_frames += 1
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pose_results = pose.process(rgb_frame)

        pose_status = "Bad pose"

        if pose_results.pose_landmarks:
            landmarks = pose_results.pose_landmarks.landmark

            # 좌표 계산
            left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
            right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
            nose = landmarks[mp_pose.PoseLandmark.NOSE]

            shoulder_center_x = (left_shoulder.x + right_shoulder.x) / 2 * width
            shoulder_center_y = (left_shoulder.y + right_shoulder.y) / 2 * height

            nose_to_shoulder_angle = np.arctan2(
                nose.y * height - shoulder_center_y,
                nose.x * width - shoulder_center_x
            ) * (180 / np.pi)

            condition_1 = 75 <= abs(nose_to_shoulder_angle) <= 115
            condition_2 = abs(shoulder_center_x - (width / 2)) <= 10

            if condition_1 and condition_2:
                pose_status = "Good pose"
                good_pose_frames += 1
                color = (0, 255, 0)  # Green
            elif not condition_1 and condition_2:
                pose_status = "Bad neck"
                bad_neck_frames += 1
                color = (0, 0, 255)  # Red
            elif condition_1 and not condition_2:
                pose_status = "Bad shoulder"
                bad_shoulder_frames += 1
                color = (255, 0, 0)  # Blue
            else:
                bad_pose_frames += 1
                color = (0, 255, 255)  # Yellow

            # 시각화 추가
            cv2.putText(frame, f"{pose_status}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            cv2.putText(frame, f"Nose-Shoulder Angle: {nose_to_shoulder_angle:.2f}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            cv2.putText(frame, f"Shoulder Center X: {shoulder_center_x:.2f}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

            cv2.line(
                frame,
                (int(left_shoulder.x * width), int(left_shoulder.y * height)),
                (int(right_shoulder.x * width), int(right_shoulder.y * height)),
                (0, 255, 0), 2
            )
            cv2.line(
                frame,
                (int(nose.x * width), int(nose.y * height)),
                (int(shoulder_center_x), int(shoulder_center_y)),
                (255, 0, 0), 2
            )

        out.write(frame)

    cap.release()
    out.release()

    # 점수 계산
    if total_frames == 0:
        raise HTTPException(status_code=400, detail="No frames to analyze.")

    bad_pose_ratio = bad_pose_frames / total_frames
    bad_neck_ratio = bad_neck_frames / total_frames
    bad_shoulder_ratio = bad_shoulder_frames / total_frames
    good_pose_ratio = good_pose_frames / total_frames

    # 점수 변환 및 계산
    base_score = 80  # 기본 점수
    bad_pose_penalty = bad_pose_ratio * 30  # 최대 30점 패널티
    bad_neck_penalty = bad_neck_ratio * 20  # 최대 20점 패널티
    bad_shoulder_penalty = bad_shoulder_ratio * 20  # 최대 20점 패널티

    final_score = base_score - (bad_pose_penalty + bad_neck_penalty + bad_shoulder_penalty)

    # 점수가 음수로 가지 않도록 제한
    final_score = max(10, final_score)

    return {
        "message": "Analysis completed.",
        "score": final_score,
        "ratios": {
            "good_pose": good_pose_ratio,
            "bad_pose": bad_pose_ratio,
            "bad_neck": bad_neck_ratio,
            "bad_shoulder": bad_shoulder_ratio
        },
        "output_video_path": output_path
    }


@router.get("/video/result")
def get_analysis_result(video_id: str):
    """
    분석 결과 조회 및 점수 확인
    """
    if video_id not in ANALYSIS_RESULTS:
        raise HTTPException(status_code=404, detail="No analysis result found for this video ID.")

    return ANALYSIS_RESULTS[video_id]

