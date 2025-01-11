from fastapi import APIRouter, Form, HTTPException
import cv2
import os
from deepface import DeepFace
from datetime import datetime
from ..utils.db_connection import get_oracle_connection
import mediapipe as mp
import numpy as np
import time

router = APIRouter()


# DeepFace 분석 함수
def analyze_emotions_in_video(video_path, int_id, intro_no):
    emotion_results = {"angry": 0, "disgust": 0, "fear": 0, "happy": 0, "sad": 0, "surprise": 0, "neutral": 0}
    frame_count = 0  # 총 프레임 수

    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception("Failed to open video file")

        print("Starting emotion analysis...")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break  # 영상이 끝났으면 종료

            frame_count += 1
            try:
                # DeepFace 감정 분석
                result = DeepFace.analyze(frame, actions=["emotion"], enforce_detection=False)

                # 결과가 리스트인지 딕셔너리인지 확인
                if isinstance(result, list):
                    result = result[0]  # 리스트의 첫 번째 요소 사용

                # 감정 데이터 추출
                if isinstance(result, dict) and "emotion" in result:
                    emotions = result["emotion"]
                    for emotion, value in emotions.items():
                        emotion_results[emotion] += value  # 감정 값 누적
                    # 프레임별 결과 출력
                    print(f"Frame {frame_count}: {emotions}")
                else:
                    print(f"Unexpected result format at frame {frame_count}: {result}")

            except Exception as e:
                print(f"Error analyzing frame {frame_count}: {e}")

        cap.release()
        print("Emotion analysis completed.")
        print(f"Total frames analyzed: {frame_count}")

    except Exception as e:
        print(f"Error processing video: {e}")
        return None

    # 평균 계산
    if frame_count > 0:
        for emotion in emotion_results:
            emotion_results[emotion] /= frame_count  # 평균값 계산

    # 평균값 출력
    print("=== Average Emotion Results ===")
    for emotion, avg_value in emotion_results.items():
        print(f"{emotion.capitalize()}: {avg_value:.2f}")

    # DB 저장
    save_emotion_analysis_to_db(emotion_results, int_id, intro_no)

    return emotion_results


# DB 저장 함수
# 감정 분석 후 DB에 저장
def save_emotion_analysis_to_db(emotion_results, int_id, intro_no):
    try:
        print("DB 함수 시작")
        print("테이블에서 조회할 값 : ", int_id)
        # Oracle DB 연결
        connection = get_oracle_connection()
        if connection is None:
            print("Database connection failed.")
            return False
        else:
            print("DB 연결 성공")

        cursor = connection.cursor()

        print("DB 조회 시작")
        # INTERVIEW_VIDEO 테이블에서 IV_ID 조회
        select_query = """
            SELECT IV_ID FROM INTERVIEW_VIDEO WHERE INT_ID = :int_id
        """

        cursor.execute(select_query, {"int_id": int_id})
        iv_id_result = cursor.fetchone()

        if not iv_id_result:
            print(f"INT_ID '{int_id}' does not exist in INTERVIEW_VIDEO.")
            return False

        # IV_ID 가져오기
        iv_id = iv_id_result[0]
        print(f"Retrieved IV_ID: {iv_id} for INT_ID: {int_id}")

        # IVF_ID 생성 (int_id + 'FEEL' + 현재 타임스탬프)
        current_timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')  # 마이크로초 포함
        ivf_id = f"{int_id}FEEL{current_timestamp}"

        # 현재 시간
        save_time = datetime.now()

        # INSERT에 사용할 값 준비
        insert_values = {
            "ivf_id": ivf_id,
            "iv_id": iv_id,
            "ivf_angry": float(emotion_results["angry"]),
            "ivf_disgust": float(emotion_results["disgust"]),
            "ivf_fear": float(emotion_results["fear"]),
            "ivf_happy": float(emotion_results["happy"]),
            "ivf_sad": float(emotion_results["sad"]),
            "ivf_surprised": float(emotion_results["surprise"]),
            "ivf_neutrality": float(emotion_results["neutral"]),
            "ivf_save_time": save_time
        }

        # 삽입할 값과 데이터 타입 출력
        print("Prepared values and their data types for INSERT:")
        for key, value in insert_values.items():
            print(f"{key}: {value} (type: {type(value)})")

        # INSERT 쿼리 작성
        insert_query = """
            INSERT INTO INTERVIEW_FEELINGS (
                IVF_ID, IV_ID, IVF_ANGRY, IVF_DISGUST, IVF_FEAR, IVF_HAPPY,
                IVF_SAD, IVF_SURPRISED, IVF_NEUTRALITY, IVF_SAVE_TIME
            ) VALUES (
                :ivf_id, :iv_id, :ivf_angry, :ivf_disgust, :ivf_fear, :ivf_happy,
                :ivf_sad, :ivf_surprised, :ivf_neutrality, :ivf_save_time
            )
        """

        # INSERT 실행
        cursor.execute(insert_query, insert_values)

        # 커밋 및 연결 해제
        connection.commit()
        cursor.close()
        connection.close()

        print(f"Emotion data successfully saved with IVF_ID: {ivf_id}")
        return True

    except Exception as e:
        print(f"Error saving to database: {e}")
        return False


# Mediapipe ------------------------------------------------------------------
# Mediapipe 초기화
mp_pose = mp.solutions.pose


def save_posture_analysis_to_db(posture_results, int_id):
    print("DB 저장 시작")
    print(f"INT_ID: {int_id}")
    try:
        print("자세 분석 결과 DB 저장 시작")

        # Oracle DB 연결
        connection = get_oracle_connection()
        if connection is None:
            print("Database connection failed.")
            return False
        else:
            print("DB 연결 성공")

        cursor = connection.cursor()

        # INTERVIEW_VIDEO 테이블에서 IV_ID 조회
        select_query = """
            SELECT IV_ID FROM INTERVIEW_VIDEO WHERE INT_ID = :int_id
        """
        cursor.execute(select_query, {"int_id": int_id})
        iv_id_result = cursor.fetchone()

        if not iv_id_result:
            print(f"INT_ID '{int_id}' does not exist in INTERVIEW_VIDEO.")
            return False

        # IV_ID 가져오기
        iv_id = iv_id_result[0]
        print(f"Retrieved IV_ID: {iv_id} for INT_ID: {int_id}")

        # IVP_ID 생성 (int_id + 'POSITION' + 현재 타임스탬프)
        current_timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')  # 마이크로초 포함
        ivp_id = f"{int_id}POSITION{current_timestamp}"

        # 현재 시간
        save_time = datetime.now()

        # INSERT에 사용할 값 준비
        insert_values = {
            "ivp_id": ivp_id,
            "iv_id": iv_id,  # 조회된 IV_ID 값
            "ivp_goodpose": float(posture_results["good_pose_percentage"]),
            "ivp_bedneck": float(posture_results["bad_neck_percentage"]),
            "ivp_bedshoulder": float(posture_results["bad_shoulder_percentage"]),
            "ivp_badpose": float(posture_results["bad_pose_percentage"]),
            "ivp_savetime": save_time
        }

        # 삽입할 값과 데이터 타입 출력
        print("Prepared values and their data types for INSERT:")
        for key, value in insert_values.items():
            print(f"{key}: {value} (type: {type(value)})")

        # INSERT 쿼리 작성
        insert_query = """
            INSERT INTO INTERVIEW_POSITION (
                IVP_ID, IV_ID, IVP_GOODPOSE, IVP_BEDNECK, IVP_BEDSHOULDER, IVP_BADPOSE, IVP_SAVETIME
            ) VALUES (
                :ivp_id, :iv_id, :ivp_goodpose, :ivp_bedneck, :ivp_bedshoulder, :ivp_badpose, :ivp_savetime
            )
        """

        # INSERT 실행
        cursor.execute(insert_query, insert_values)

        # 커밋 및 연결 해제
        connection.commit()
        cursor.close()
        connection.close()

        print(f"Posture analysis data successfully saved with IVP_ID: {ivp_id}")
        return True

    except Exception as e:
        print(f"Error saving posture analysis to database: {e}")
        return False


# 자세 분석 함수에서 DB 저장 호출
def analyze_posture_in_video(video_path, int_id):
    print("자세 분석 시작")
    print(int_id)
    pose = mp_pose.Pose(min_detection_confidence=0.8, min_tracking_confidence=0.8)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise Exception("Failed to open video file")

    print("자세분석 시작 Starting posture analysis...")

    frame_count = 0
    good_pose_count = 0
    bad_neck_count = 0
    bad_shoulder_count = 0
    bad_pose_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        frame_height, frame_width, _ = frame.shape
        center_x, center_y = frame_width / 2, frame_height / 2
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Mediapipe Pose 처리
        pose_results = pose.process(rgb_frame)
        condition_1 = False
        condition_2 = False
        pose_status = "Pose not detected"

        if pose_results.pose_landmarks:
            landmarks = pose_results.pose_landmarks.landmark

            # 어깨와 코의 좌표
            left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
            right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
            nose = landmarks[mp_pose.PoseLandmark.NOSE]

            # 어깨 중앙점 계산
            shoulder_center_x = (left_shoulder.x + right_shoulder.x) / 2 * frame_width
            shoulder_center_y = (left_shoulder.y + right_shoulder.y) / 2 * frame_height

            # 어깨 중앙점이 화면 중앙에 가까운지 확인
            if abs(shoulder_center_x - center_x) <= 10:
                condition_2 = True

            # 코와 어깨 중앙점 간의 각도 계산
            nose_to_shoulder_angle = np.arctan2(
                nose.y * frame_height - shoulder_center_y,
                nose.x * frame_width - shoulder_center_x
            ) * (180 / np.pi)

            if 80 <= abs(nose_to_shoulder_angle) <= 100:
                condition_1 = True

            # 자세 평가
            if condition_1 and condition_2:
                pose_status = "Good pose"
                good_pose_count += 1
            elif not condition_1 and condition_2:
                pose_status = "Bad neck"
                bad_neck_count += 1
            elif condition_1 and not condition_2:
                pose_status = "Bad shoulder"
                bad_shoulder_count += 1
            else:
                pose_status = "Bad pose"
                bad_pose_count += 1

        # 프레임별 자세 상태 출력
        print(f"Frame {frame_count}: Pose status -> {pose_status}")

    cap.release()
    pose.close()

    print("자세 분석 끝 Posture analysis completed.")
    print(f"Total frames analyzed: {frame_count}")
    print(f"Good poses: {good_pose_count}")
    print(f"Bad neck: {bad_neck_count}")
    print(f"Bad shoulder: {bad_shoulder_count}")
    print(f"Bad poses: {bad_pose_count}")

    # 백분율 계산
    total_pose_count = good_pose_count + bad_neck_count + bad_shoulder_count + bad_pose_count
    posture_results = {
        "good_pose_percentage": (good_pose_count / total_pose_count) * 100 if total_pose_count > 0 else 0.0,
        "bad_neck_percentage": (bad_neck_count / total_pose_count) * 100 if total_pose_count > 0 else 0.0,
        "bad_shoulder_percentage": (bad_shoulder_count / total_pose_count) * 100 if total_pose_count > 0 else 0.0,
        "bad_pose_percentage": (bad_pose_count / total_pose_count) * 100 if total_pose_count > 0 else 0.0,
    }

    # 백분율 출력
    print("\n=== Pose Percentage Analysis ===")
    for key, value in posture_results.items():
        print(f"{key.replace('_', ' ').capitalize()}: {value:.5f}%")

    # DB 저장
    save_posture_analysis_to_db(posture_results, int_id)

    return posture_results


# Mediapipe 초기화
mp_face_mesh = mp.solutions.face_mesh


# 시선 분석 함수
# 시선 분석 함수
def analyze_gaze_in_video(video_path, int_id):
    print("시선 분석 시작 Starting gaze analysis...")
    face_mesh = mp_face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=True)
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise Exception("Failed to open video file")

    frame_count = 0
    prev_left_eye = None
    prev_right_eye = None
    eye_movement_list = []
    start_time = time.time()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        frame_height, frame_width, _ = frame.shape
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb_frame)

        eye_movement = 0
        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                # 왼쪽 눈과 오른쪽 눈 랜드마크
                left_eye_landmarks = [face_landmarks.landmark[i] for i in range(133, 144)]
                right_eye_landmarks = [face_landmarks.landmark[i] for i in range(362, 373)]

                # 좌표 계산
                left_eye_coords = [(int(lm.x * frame_width), int(lm.y * frame_height)) for lm in left_eye_landmarks]
                right_eye_coords = [(int(lm.x * frame_width), int(lm.y * frame_height)) for lm in right_eye_landmarks]

                # 눈 이동률 계산
                if prev_left_eye is not None and prev_right_eye is not None:
                    left_eye_diff = np.linalg.norm(np.array(left_eye_coords) - np.array(prev_left_eye))
                    right_eye_diff = np.linalg.norm(np.array(right_eye_coords) - np.array(prev_right_eye))
                    eye_movement = (left_eye_diff + right_eye_diff) / 2
                    eye_movement_list.append(eye_movement)

                prev_left_eye = left_eye_coords
                prev_right_eye = right_eye_coords

        # 프레임별 시선 이동 출력
        print(f"Frame {frame_count}: Eye Movement -> {eye_movement:.5f}")

    cap.release()
    face_mesh.close()

    print("시선 분석 완료 Gaze analysis completed.")
    if eye_movement_list:
        avg_movement = np.mean(eye_movement_list)
        max_movement = np.max(eye_movement_list)
        min_movement = np.min(eye_movement_list)

        # 결과 출력
        print(f"평균 이동률: {avg_movement:.5f}")
        print(f"최대 이동률: {max_movement:.5f}")
        print(f"최소 이동률: {min_movement:.5f}")
    else:
        avg_movement = max_movement = min_movement = 0.0

    # DB 저장
    save_gaze_analysis_to_db(avg_movement, max_movement, min_movement, int_id)

    return {
        "average_movement": avg_movement,
        "max_movement": max_movement,
        "min_movement": min_movement,
    }


# DB 저장 함수
def save_gaze_analysis_to_db(avg_movement, max_movement, min_movement, int_id):
    print("DB 저장 시작")
    try:
        # Oracle DB 연결
        connection = get_oracle_connection()
        if connection is None:
            print("Database connection failed.")
            return False

        cursor = connection.cursor()

        # INTERVIEW_VIDEO 테이블에서 IV_ID 조회
        select_query = """
            SELECT IV_ID FROM INTERVIEW_VIDEO WHERE INT_ID = :int_id
        """
        cursor.execute(select_query, {"int_id": int_id})
        iv_id_result = cursor.fetchone()

        if not iv_id_result:
            print(f"INT_ID '{int_id}' does not exist in INTERVIEW_VIDEO.")
            return False

        # IV_ID 가져오기
        iv_id = iv_id_result[0]
        print(f"Retrieved IV_ID: {iv_id} for INT_ID: {int_id}")

        # IVG_ID 생성 (int_id + 'GAZE' + 현재 타임스탬프)
        current_timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')  # 마이크로초 포함
        ivg_id = f"{int_id}GAZE{current_timestamp}"

        # 현재 시간
        save_time = datetime.now()

        # INSERT에 사용할 값 준비
        insert_values = {
            "ivg_id": ivg_id,
            "iv_id": iv_id,
            "ivg_avg": float(avg_movement),
            "ivg_min": float(min_movement),
            "ivg_max": float(max_movement),
            "ivg_save_time": save_time
        }

        # 삽입할 값과 데이터 타입 출력
        print("Prepared values and their data types for INSERT:")
        for key, value in insert_values.items():
            print(f"{key}: {value} (type: {type(value)})")

        # INSERT 쿼리 작성
        insert_query = """
            INSERT INTO INTERVIEW_GAZE (
                IVG_ID, IV_ID, IVG_AVG, IVG_MIN, IVG_MAX, IVG_SAVE_TIME
            ) VALUES (
                :ivg_id, :iv_id, :ivg_avg, :ivg_min, :ivg_max, :ivg_save_time
            )
        """

        # INSERT 실행
        cursor.execute(insert_query, insert_values)

        # 커밋 및 연결 해제
        connection.commit()
        cursor.close()
        connection.close()

        print(f"Gaze analysis data successfully saved with IVG_ID: {ivg_id}")
        return True

    except Exception as e:
        print(f"Error saving gaze analysis to database: {e}")
        return False

# FastAPI 엔드포인트
@router.post("/analysis")
async def analyze_video(videoFilename: str = Form(...), introNo: str = Form(...), roundId: str = Form(...),
                        intId: str = Form(...)):
    print("비디오 분석 시작")
    print(f"Received data -> videoFilename: {videoFilename}, introNo: {introNo}, roundId: {roundId}, intId: {intId}")

    video_path = f'C:\\JOBISIMG\\VIDEO\\{videoFilename}'

    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    print(f"파일존재 : Analyzing video file: {videoFilename}")

    emotion_analysis = analyze_emotions_in_video(video_path, intId, introNo)
    if emotion_analysis is None:
        raise HTTPException(status_code=500, detail="Failed to analyze emotions in the video")

    print(f"감정 분석 결과 : Emotion analysis results: {emotion_analysis}")

    posture_analysis = analyze_posture_in_video(video_path, intId)
    print(f"자세 분석 결과 : Posture analysis results: {posture_analysis}")

    gaze_analysis = analyze_gaze_in_video(video_path, intId)
    print(f"시선 분석 결과 : Gaze analysis results: {gaze_analysis}")

    return {
        "status": "success",
        "message": "VIDEO 감정, 자세, 시선 분석 완료",
        "emotionAnalysis": emotion_analysis,
        "postureAnalysis": posture_analysis,
        "gazeAnalysis": gaze_analysis,
    }
