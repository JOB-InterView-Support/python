from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import cv2
import pyaudio
import wave
import threading
import time
import os
from pydub import AudioSegment
from app.utils.db_connection import get_oracle_connection

from pydantic import BaseModel

router = APIRouter()

# 전역 변수
is_recording = False
recording_lock = threading.Lock()
# 경로 설정
BASE_PATH = "C:/JOBISIMG"
AUDIO_PATH = os.path.join(BASE_PATH, "audio")
VIDEO_PATH = os.path.join(BASE_PATH, "video")

# 폴더 생성 함수
def create_directory():
    if not os.path.exists(BASE_PATH):
        os.makedirs(BASE_PATH, exist_ok=True)
    if not os.path.exists(AUDIO_PATH):
        os.makedirs(AUDIO_PATH, exist_ok=True)
    if not os.path.exists(VIDEO_PATH):
        os.makedirs(VIDEO_PATH, exist_ok=True)

def save_interview_to_db(uuid, intro_no, round_id, int_id):
    """Oracle DB에 인터뷰 데이터를 저장하는 함수"""
    connection = get_oracle_connection()
    if not connection:
        print("Failed to connect to the database.")
        return False

    try:
        cursor = connection.cursor()
        insert_query = """
        INSERT INTO INTERVIEW (INT_ID, INTRO_NO, INT_DATE, INTERVIEW_ROUND, INT_IS_DELETED)
        VALUES (:int_id, :intro_no, SYSDATE, :round_id, 'N')
        """
        cursor.execute(insert_query, {
            "int_id": int_id,  # int_id 추가
            "intro_no": intro_no,
            "round_id": round_id
        })
        connection.commit()
        print(f"Successfully saved interview with ID {int_id}")
        return True
    except Exception as e:
        print(f"Failed to save interview to the database: {e}")
        return False
    finally:
        connection.close()


# 카메라 스트리밍 및 녹화 함수
def stream_and_record_video(video_filename):
    global is_recording, current_frame, lock

    try:
        # 카메라 초기화
        #camera_index = get_camera_index()
        #cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 20)
        if not cap.isOpened():
            raise RuntimeError("Failed to open the camera.")
        print("Camera successfully initialized.")
    except RuntimeError as e:
        print(f"Error initializing camera: {e}")
        return

    # 비디오 파일 저장 설정
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_filename, fourcc, 20.0, (640, 480))
    if not out.isOpened():
        print("Error initializing VideoWriter. Check codec and file path.")
        cap.release()
        return

    frame_count = 0  # 디버깅용 프레임 수 카운트

    while is_recording:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame from camera. Stopping recording.")
            break

        # 좌우 반전 처리
        frame = cv2.flip(frame, 1)

        # 현재 프레임 저장 (스트리밍을 위해)
        with lock:
            current_frame = frame

        # 녹화 저장
        out.write(frame)
        frame_count += 1
        if frame_count % 50 == 0:  # 50프레임마다 로그 출력
            print(f"Recorded {frame_count} frames so far.")

    cap.release()
    out.release()

    if os.path.exists(video_filename):
        print(f"Video saved successfully to {video_filename}. File size: {os.path.getsize(video_filename)} bytes")
    else:
        print("Video file was not saved. Please check the VideoWriter configuration.")

def record_audio(audio_filename_wav, audio_filename_mp3, duration=120):
    global is_recording

    chunk = 1024
    sample_format = pyaudio.paInt16
    channels = 1
    rate = 44100
    audio = pyaudio.PyAudio()

    try:
        stream = audio.open(format=sample_format,
                            channels=channels,
                            rate=rate,
                            input=True,
                            frames_per_buffer=chunk)
        print("Audio stream successfully opened.")
    except Exception as e:
        print(f"Error opening audio stream: {e}")
        return

    frames = []
    start_time = time.time()

    while is_recording:
        if time.time() - start_time > duration:  # 정확히 duration 초 후 종료
            is_recording = False
            break
        try:
            data = stream.read(chunk, exception_on_overflow=False)
            frames.append(data)
        except Exception as e:
            print(f"Error capturing audio: {e}")
            break

    stream.stop_stream()
    stream.close()
    audio.terminate()

    wf = wave.open(audio_filename_wav, "wb")
    wf.setnchannels(channels)
    wf.setsampwidth(audio.get_sample_size(sample_format))
    wf.setframerate(rate)
    wf.writeframes(b"".join(frames))
    wf.close()
    print(f"Audio saved to {audio_filename_wav}")

    try:
        sound = AudioSegment.from_wav(audio_filename_wav)
        sound.export(audio_filename_mp3, format="mp3")
        print(f"Audio converted to MP3: {audio_filename_mp3}")
        os.remove(audio_filename_wav)
    except Exception as e:
        print(f"Error converting audio to MP3: {e}")

class InterviewRequest(BaseModel):
    uuid: str
    intro_no: str
    round_id: str
    int_id: str

# 녹화 시작 엔드포인트
@router.post("/record/start")
def start_recording(request: InterviewRequest):
    global is_recording

    try:
        with recording_lock:
            if is_recording:
                raise HTTPException(status_code=400, detail="Recording is already in progress.")

            # DB에 인터뷰 데이터 저장 (4개 인자 전달)
            if not save_interview_to_db(request.uuid, request.intro_no, request.round_id, request.int_id):
                raise HTTPException(status_code=500, detail="Failed to save interview to the database.")

            create_directory()
            audio_filename_wav = os.path.join(AUDIO_PATH, f"{request.uuid}_{request.intro_no}_interview_{request.round_id}_{request.int_id}.wav")
            audio_filename_mp3 = os.path.join(AUDIO_PATH, f"{request.uuid}_{request.intro_no}_interview_{request.round_id}_{request.int_id}.mp3")
            video_filename = os.path.join(VIDEO_PATH, f"{request.uuid}_{request.intro_no}_interview_{request.round_id}_{request.int_id}.mp4")

            # 녹화 및 녹음 시작
            is_recording = True
            video_thread = threading.Thread(target=stream_and_record_video, args=(video_filename,))
            audio_thread = threading.Thread(target=record_audio, args=(audio_filename_wav, audio_filename_mp3))
            video_thread.start()
            audio_thread.start()

        return JSONResponse(content={"message": "Recording started.", "uuid": request.uuid, "int_id": request.int_id})

    except Exception as e:
        print(f"Error during recording process: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# 녹화 중지 엔드포인트
@router.post("/record/stop")
def stop_recording():
    global is_recording

    with recording_lock:
        if not is_recording:
            raise HTTPException(status_code=400, detail="No recording is in progress.")

        is_recording = False  # 녹화를 중단

    return JSONResponse(content={"message": "Recording stopped."})
