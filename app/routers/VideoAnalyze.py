from fastapi import APIRouter, Form, HTTPException
import cv2
import os
from deepface import DeepFace
#from VideoEmotions import calculate_emotion_score

router = APIRouter()

@router.post("/analysis")
async def analyze_video(videoFilename: str = Form(...), introNo: str = Form(...), roundId: str = Form(...), intId: str = Form(...)):
    video_path = f'C:\\JOBISIMG\\VIDEO\\{videoFilename}'
    video_exists = os.path.exists(video_path)
    print(f"영상 파일 존재 Video File: {videoFilename} Exists: {video_exists}")
    return {"videoFilename": videoFilename, "exists": video_exists, "introNo": introNo, "roundId": roundId, "intId": intId}


BASE_DIRECTORY = r"C:\JOBISIMG\VIDEO"
ANALYSIS_DIRECTORY = r"C:\JOBISIMG\ANALYSIS"
FEELINGS_ANALYSIS_RESULTS = {}


def calculate_emotion_score(emotion_averages):
    # 감정 점수 계산 로직
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

    # 부정적 감정 감점
    disgust_penalty = disgust * 0.3
    angry_penalty = angry * 0.3
    sad_penalty = sad * 0.3
    fear_penalty = fear * 0.2
    surprise_penalty = max(0, (surprise - 5) * 0.1)
    neutral_penalty = max(0, (neutral - 85) * 0.2)

    base_score = 80
    raw_score = base_score + neutral_score + happy_score - (
        disgust_penalty + angry_penalty + sad_penalty + fear_penalty + surprise_penalty + neutral_penalty
    )

    # 정규화
    min_raw_score = base_score - (30 + 30 + 30 + 20 + 10 + 10)
    max_raw_score = base_score + (50 + 30)

    final_score = 10 + ((raw_score - min_raw_score) / (max_raw_score - min_raw_score)) * 90
    return max(10, min(100, final_score))



def pose_analyze_video(videoFilename: str):
    """
    저장된 비디오 파일 감정 분석
    """
    video_path = os.path.join(BASE_DIRECTORY, videoFilename)
    print("감정 분석")
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found.")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Unable to open video for analysis.")

    # 결과 비디오 저장 경로
    analyzed_video_name = f"{os.path.splitext(videoFilename)[0]}_analyzed.mp4"
    output_path = os.path.join(ANALYSIS_DIRECTORY, analyzed_video_name)
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
            # DeepFace 감정 분석
            analysis = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
            emotions = analysis[0]['emotion']

            # 감정별 통계 누적
            for emotion, score in emotions.items():
                emotion_results[emotion] = emotion_results.get(emotion, 0) + score

            # 주요 감정 표시
            dominant_emotion = analysis[0]['dominant_emotion']
            cv2.putText(frame, f"Dominant Emotion: {dominant_emotion}", (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        except Exception:
            cv2.putText(frame, "No face detected", (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        out.write(frame)

    cap.release()
    out.release()

    if total_frames == 0:
        raise HTTPException(status_code=400, detail="No frames to analyze.")

    # 감정 평균 및 점수 계산
    averaged_emotions = {emotion: score / total_frames for emotion, score in emotion_results.items()}
    final_score = calculate_emotion_score(averaged_emotions)

    # 결과 저장
    FEELINGS_ANALYSIS_RESULTS[videoFilename] = {
        "emotions": averaged_emotions,
        "final_score": final_score,
        "output_video_path": output_path
    }

    return {
        "message": "Feelings Analysis completed.",
        "emotions": averaged_emotions,
        "final_score": final_score,
        "output_video_path": output_path
    }
