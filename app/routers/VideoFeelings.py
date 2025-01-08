from fastapi import FastAPI, APIRouter, HTTPException
from datetime import datetime
import cv2
from deepface import DeepFace
import os
from pydantic import BaseModel

app = FastAPI(docs_url="/docs", redoc_url="/redoc")
router = APIRouter()

BASE_DIRECTORY = r"D:\ik\study\프로젝트\JOBIS\videosave_test"
ANALYSIS_DIRECTORY = r"D:\ik\study\프로젝트\JOBIS\analysis_test"

# 분석 결과 저장
FEELINGS_ANALYSIS_RESULTS = {}

class VideoRequest(BaseModel):
    prefix: str

def calculate_emotion_score(emotion_averages):
    neutral = emotion_averages.get('neutral', 0)
    happy = emotion_averages.get('happy', 0)
    disgust = emotion_averages.get('disgust', 0)
    angry = emotion_averages.get('angry', 0)
    sad = emotion_averages.get('sad', 0)
    fear = emotion_averages.get('fear', 0)
    surprise = emotion_averages.get('surprise', 0)

    # 긍정적 감정 점수
    neutral_score = min(neutral, 50) * 0.4
    happy_score = min(happy, 30) * 0.3

    # 부정적 감정 감점 (강화)
    disgust_penalty = disgust * 0.3
    angry_penalty = angry * 0.3
    sad_penalty = sad * 0.3
    fear_penalty = fear * 0.2
    surprise_penalty = max(0, (surprise - 5) * 0.1)

    # neutral 비율 초과 시 감점
    neutral_penalty = max(0, (neutral - 85) * 0.2)

    # 점수 계산
    base_score = 80
    raw_score = base_score + neutral_score + happy_score - (
        disgust_penalty + angry_penalty + sad_penalty + fear_penalty + surprise_penalty + neutral_penalty
    )

    # 정규화 (10 ~ 100점 기준으로 변경함)
    min_raw_score = base_score - (30 + 30 + 30 + 20 + 10 + 10)  # 최저 점수
    max_raw_score = base_score + (50 + 30)  # 최고 점수

    final_score = 10 + ((raw_score - min_raw_score) / (max_raw_score - min_raw_score)) * 90
    return max(10, min(100, final_score))


@router.post("/record")
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

        elapsed_time = (datetime.now() - start_time).total_seconds()
        if elapsed_time >= 20:
            break

    cap.release()
    out.release()

    return {"message": "Video saved successfully.", "video_id": video_id, "video_path": video_path}


@router.get("/list")
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


@router.post("/analyze")
def analyze_video(video_id: str):
    """
    저장된 면접영상 분석 및 감정 분석 결과 평균값 추출
    """
    video_path = os.path.join(BASE_DIRECTORY, f"{video_id}.mp4")
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found.")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Unable to open video for analysis.")

    output_path = os.path.join(ANALYSIS_DIRECTORY, f"{video_id.replace('recordtest_', '')}_feelings_analyzed.mp4")
    os.makedirs(ANALYSIS_DIRECTORY, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    total_frames = 0
    emotion_results = {}

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        total_frames += 1

        try:
            # DeepFace - 감정 분석
            analysis = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
            emotions = analysis[0]['emotion']

            # 감정별 통계 누적
            for emotion, score in emotions.items():
                if emotion not in emotion_results:
                    emotion_results[emotion] = 0
                emotion_results[emotion] += score

            # 결과 비디오에 표시하기
            dominant_emotion = analysis[0]['dominant_emotion']
            cv2.putText(frame, f"Dominant Emotion: {dominant_emotion}", (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        except Exception as e:
            cv2.putText(frame, "No face detected", (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        out.write(frame)

    cap.release()
    out.release()

    if total_frames == 0:
        raise HTTPException(status_code=400, detail="No frames to analyze.")

    # 감정 평균 / 점수 계산
    averaged_emotions = {emotion: score / total_frames for emotion, score in emotion_results.items()}
    final_score = calculate_emotion_score(averaged_emotions)

    return {
        "message": "Feelings Analysis completed.",
        "emotions": averaged_emotions,
        "final_score": final_score,
        "output_video_path": output_path
    }

# DB 연결 예정임
@router.get("/result")
def get_analysis_result(video_id: str):
    """
    분석 결과 조회
    """
    if video_id not in FEELINGS_ANALYSIS_RESULTS:
        raise HTTPException(status_code=404, detail="No analysis result found for this video ID.")

    return FEELINGS_ANALYSIS_RESULTS[video_id]