from fastapi import FastAPI, APIRouter, HTTPException
from datetime import datetime
import cv2
import mediapipe as mp
import os
from pydantic import BaseModel

app = FastAPI(docs_url="/docs", redoc_url="/redoc")
router = APIRouter()

BASE_DIRECTORY = r"D:\ik\study\프로젝트\JOBIS\videosave_test"
ANALYSIS_DIRECTORY = r"D:\ik\study\프로젝트\JOBIS\analysis_test"

# Mediapipe 초기화
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.8, min_tracking_confidence=0.8)

class VideoRequest(BaseModel):
    video_id: str  # 비디오 ID

POSE_ANALYSIS_RESULTS = {}


@router.post("/record")
def pose_save_video():
    """
    원본 비디오 저장 기능
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

        elapsed_time = (datetime.now() - start_time).total_seconds()
        if elapsed_time >= 20 or (cv2.waitKey(1) & 0xFF == 27):  # ESC로 종료
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()

    return {"message": "Video saved successfully.", "video_id": video_id, "video_path": video_path}


@router.get("/list")
def pose_list_videos():
    """
    저장된 비디오 목록 조회
    """
    if not os.path.exists(BASE_DIRECTORY):
        return {"message": "No videos found.", "videos": []}

    video_files = [
        f for f in os.listdir(BASE_DIRECTORY)
        if os.path.isfile(os.path.join(BASE_DIRECTORY, f)) and f.endswith(".mp4")
    ]

    return {"message": "Video list retrieved successfully.", "videos": video_files}


@router.post("/analyze")
def pose_analyze_video(request: VideoRequest):
    """
    저장된 비디오 분석 및 시각화 저장
    """
    video_id = request.video_id
    video_path = os.path.join(BASE_DIRECTORY, f"{video_id}.mp4")
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found.")

    os.makedirs(ANALYSIS_DIRECTORY, exist_ok=True)
    analyzed_video_path = os.path.join(ANALYSIS_DIRECTORY, f"{video_id}_analyzed.mp4")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Unable to open video for analysis.")

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(analyzed_video_path, fourcc, fps, (frame_width, frame_height))

    total_frames = 0
    pose_status_count = {"Good pose": 0, "Bad pose": 0}

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        total_frames += 1
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb_frame)

        pose_status = "Bad pose"

        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark

            for landmark in landmarks:
                x = int(landmark.x * frame_width)
                y = int(landmark.y * frame_height)
                cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)

            # 간단한 조건 기반 자세 판별
            left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
            right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
            nose = landmarks[mp_pose.PoseLandmark.NOSE]

            shoulder_center_x = (left_shoulder.x + right_shoulder.x) / 2 * frame_width

            if abs(shoulder_center_x - (frame_width / 2)) < 20:
                pose_status = "Good pose"

            pose_status_count[pose_status] += 1

        cv2.putText(frame, f"{pose_status}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        out.write(frame)

    cap.release()
    out.release()

    POSE_ANALYSIS_RESULTS[video_id] = {
        "total_frames": total_frames,
        "pose_status_count": pose_status_count
    }

    return {"message": "Video analyzed and saved successfully.", "analyzed_video_path": analyzed_video_path}

# DB 연결 예정임
@router.get("/result")
def pose_analysis_result(video_id: str):
    """
    분석 결과 조회
    """
    if video_id not in POSE_ANALYSIS_RESULTS:
        raise HTTPException(status_code=404, detail="No analysis result found for this video ID.")

    result = POSE_ANALYSIS_RESULTS[video_id]
    total_frames = result["total_frames"]
    good_pose_count = result["pose_status_count"]["Good pose"]
    bad_pose_count = result["pose_status_count"]["Bad pose"]

    good_pose_ratio = (good_pose_count / total_frames) * 100
    bad_pose_ratio = (bad_pose_count / total_frames) * 100

    return {
        "message": "Analysis result retrieved successfully.",
        "video_id": video_id,
        "total_frames": total_frames,
        "good_pose_ratio": good_pose_ratio,
        "bad_pose_ratio": bad_pose_ratio
    }