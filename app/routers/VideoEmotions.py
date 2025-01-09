from fastapi import FastAPI, APIRouter, HTTPException
from datetime import datetime
import cv2
from deepface import DeepFace
import os
from app.utils.db_connection import get_oracle_connection

app = FastAPI(docs_url="/docs", redoc_url="/redoc")
router = APIRouter()

BASE_DIRECTORY = r"D:\ik\study\프로젝트\JOBIS\videosave_test"
ANALYSIS_DIRECTORY = r"D:\ik\study\프로젝트\JOBIS\analysis_test"

# 분석 결과 저장
FEELINGS_ANALYSIS_RESULTS = {}

def calculate_emotion_score(emotion_averages):
    """
    감정 점수 계산 함수
    """
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

    min_raw_score = base_score - (30 + 30 + 30 + 20 + 10 + 10)
    max_raw_score = base_score + (50 + 30)

    final_score = 10 + ((raw_score - min_raw_score) / (max_raw_score - min_raw_score)) * 90
    return max(10, min(100, final_score))


def save_emotions_to_db(iv_id, int_id, emotions):
    """
    감정 데이터를 INTERVIEW_FEELINGS 테이블에 저장
    """
    try:
        connection = get_oracle_connection()
        cursor = connection.cursor()

        query = """
        INSERT INTO INTERVIEW_FEELINGS (
            IVF_ID, IV_ID, IVF_ANGRY, IVF_DISGUST, IVF_FEAR,
            IVF_HAPPY, IVF_SAD, IVF_SURPRISED, IVF_NEUTRALITY, IVF_SAVE_TIME
        ) VALUES (
            :ivf_id, :iv_id, :ivf_angry, :ivf_disgust, :ivf_fear,
            :ivf_happy, :ivf_sad, :ivf_surprised, :ivf_neutrality, :ivf_save_time
        )
        """
        cursor.execute(query, {
            "ivf_id": f"{iv_id}_feelings",
            "iv_id": iv_id,
            "ivf_angry": emotions.get("angry", 0),
            "ivf_disgust": emotions.get("disgust", 0),
            "ivf_fear": emotions.get("fear", 0),
            "ivf_happy": emotions.get("happy", 0),
            "ivf_sad": emotions.get("sad", 0),
            "ivf_surprised": emotions.get("surprise", 0),
            "ivf_neutrality": emotions.get("neutral", 0),
            "ivf_save_time": datetime.utcnow(),
        })
        connection.commit()
        print(f"감정 결과 저장 완료: IVF_ID={iv_id}_feelings")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB 저장 실패: {e}")
    finally:
        cursor.close()
        connection.close()


@router.post("/analyze")
def emotions_analyze_video(video_id: str, int_id: str):
    """
    저장된 면접영상 분석 및 감정 분석 결과 평균값 추출
    """
    video_path = os.path.join(BASE_DIRECTORY, f"{video_id}.mp4")
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found.")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Unable to open video for analysis.")

    output_path = os.path.join(ANALYSIS_DIRECTORY, f"{video_id}_analyzed.mp4")
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

    # DB 저장
    save_emotions_to_db(video_id, int_id, averaged_emotions)

    FEELINGS_ANALYSIS_RESULTS[video_id] = {
        "emotions": averaged_emotions,
        "final_score": final_score,
        "output_video_path": output_path
    }

    return {
        "message": "Feelings Analysis completed and saved to database.",
        "emotions": averaged_emotions,
        "final_score": final_score,
        "output_video_path": output_path
    }


@router.get("/result")
def emotions_analysis_result(video_id: str):
    """
    분석 결과 조회
    """
    if video_id not in FEELINGS_ANALYSIS_RESULTS:
        raise HTTPException(status_code=404, detail="No analysis result found for this video ID.")

    return FEELINGS_ANALYSIS_RESULTS[video_id]