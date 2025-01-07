# # from fastapi import APIRouter, WebSocket
# # import cv2
# # import pyaudio
# # import wave
# # import threading
# # import time
# # import os
# #
# # router = APIRouter()
#
# # # 녹화와 녹음을 제어하기 위한 상태 변수
# # is_recording = False
# #
# # # 경로 및 파일 설정
# # BASE_PATH = "C:/JOBISIMG"
# #
# # def create_directory(uuid, intro_no, round_id):
# #     """폴더를 생성하는 함수"""
# #     folder_name = f"{uuid}_{intro_no}_interview_{round_id}"
# #     folder_path = os.path.join(BASE_PATH, folder_name)
# #     os.makedirs(folder_path, exist_ok=True)
# #     return folder_path
# #
# # # OpenCV를 사용한 캠 녹화
# # def record_video(folder_path):
# #     global is_recording
# #     video_filename = os.path.join(folder_path, "video.mp4")
# #     cap = cv2.VideoCapture(0)
# #     fourcc = cv2.VideoWriter_fourcc(*"mp4v")
# #     out = cv2.VideoWriter(video_filename, fourcc, 20.0, (640, 480))
# #
# #     while is_recording:
# #         ret, frame = cap.read()
# #         if ret:
# #             out.write(frame)
# #
# #     cap.release()
# #     out.release()
# #
# # # PyAudio를 사용한 마이크 녹음
# # def record_audio(folder_path):
# #     global is_recording
# #     audio_filename = os.path.join(folder_path, "audio.mp3")
# #     chunk = 1024  # 프레임 크기
# #     sample_format = pyaudio.paInt16  # 16비트 오디오
# #     channels = 1  # 채널 수 (모노)
# #     rate = 44100  # 샘플링 레이트
# #     audio = pyaudio.PyAudio()
# #
# #     stream = audio.open(format=sample_format,
# #                         channels=channels,
# #                         rate=rate,
# #                         input=True,
# #                         frames_per_buffer=chunk)
# #
# #     frames = []
# #
# #     while is_recording:
# #         data = stream.read(chunk)
# #         frames.append(data)
# #
# #     stream.stop_stream()
# #     stream.close()
# #     audio.terminate()
# #
# #     # 녹음된 데이터를 MP3 형식으로 저장
# #     wf = wave.open(audio_filename, "wb")
# #     wf.setnchannels(channels)
# #     wf.setsampwidth(audio.get_sample_size(sample_format))
# #     wf.setframerate(rate)
# #     wf.writeframes(b"".join(frames))
# #     wf.close()
# #
# # # WebSocket 엔드포인트
# # @router.websocket("/record")
# # async def record_endpoint(websocket: WebSocket):
# #     global is_recording
# #     await websocket.accept()
# #
# #     # WebSocket에서 uuid, intro_no, round_id 받기
# #     data = await websocket.receive_json()
# #     uuid = data.get("uuid")
# #     intro_no = data.get("intro_no")
# #     round_id = data.get("round_id")
# #
# #     if not all([uuid, intro_no, round_id]):
# #         await websocket.send_text("Missing required parameters (uuid, intro_no, round_id).")
# #         await websocket.close()
# #         return
# #
# #     # 폴더 생성
# #     folder_path = create_directory(uuid, intro_no, round_id)
# #
# #     # 녹화 및 녹음 시작
# #     is_recording = True
# #     video_thread = threading.Thread(target=record_video, args=(folder_path,))
# #     audio_thread = threading.Thread(target=record_audio, args=(folder_path,))
# #     video_thread.start()
# #     audio_thread.start()
# #
# #     # 2번 반복 테스트용
# #     total_duration = 2 * (20 + 40)  # 2번의 20초 + 40초 반복
# #
# #     # 8번 반복 코드 (주석처리)
# #     # total_duration = 8 * (20 + 40)  # 8번의 20초 + 40초 반복
# #
# #     time.sleep(total_duration)
# #
# #     # 녹화 및 녹음 종료
# #     is_recording = False
# #     video_thread.join()
# #     audio_thread.join()
# #
# #     await websocket.send_text(f"Recording and audio capturing finished! Files saved to {folder_path}")
# #     await websocket.close()
#
# # ============
# #
# from fastapi import APIRouter
# import cv2
# import pyaudio
# import wave
# import threading
# import time
# import os
# from pydub import AudioSegment
#
# router = APIRouter()
#
# # 녹화와 녹음을 제어하기 위한 상태 변수
# is_recording = False
#
# # 경로 및 파일 설정
# BASE_PATH = "C:/JOBISIMG"
# AUDIO_PATH = os.path.join(BASE_PATH, "audio")
# VIDEO_PATH = os.path.join(BASE_PATH, "video")
#
# def create_directory(uuid, intro_no, round_id):
#     """폴더를 생성하는 함수"""
#     folder_name = f"{uuid}_{intro_no}_interview_{round_id}"
#     folder_path = os.path.join(BASE_PATH, folder_name)
#     os.makedirs(folder_path, exist_ok=True)
#     return folder_path
#
# def get_camera_index():
#     """사용 가능한 카메라 인덱스를 반환"""
#     for index in range(5):  # 최대 5개의 카메라 인덱스 확인
#         cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
#         if cap.read()[0]:
#             cap.release()
#             return index
#         cap.release()
#     raise RuntimeError("No available camera found.")
#
# # OpenCV를 사용한 캠 녹화
# def record_video(folder_path):
#     global is_recording
#     video_filename = os.path.join(folder_path, "video.mp4")
#
#     try:
#         camera_index = get_camera_index()
#         cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)  # DirectShow 백엔드 사용
#     except RuntimeError as e:
#         print(f"Error finding camera: {e}")
#         return
#
#     fourcc = cv2.VideoWriter_fourcc(*"mp4v")
#     out = cv2.VideoWriter(video_filename, fourcc, 20.0, (640, 480))
#
#     while is_recording:
#         ret, frame = cap.read()
#         if not ret:
#             print("Failed to read frame from camera. Stopping recording.")
#             break
#         out.write(frame)
#
#     cap.release()
#     out.release()
#     print(f"Video saved to {video_filename}")
#
# # PyAudio를 사용한 마이크 녹음
# def record_audio(folder_path):
#     global is_recording
#     audio_filename_wav = os.path.join(folder_path, "audio.wav")
#     audio_filename_mp3 = os.path.join(folder_path, "audio.mp3")
#     chunk = 1024  # 프레임 크기
#     sample_format = pyaudio.paInt16  # 16비트 오디오
#     channels = 1  # 채널 수 (모노)
#     rate = 44100  # 샘플링 레이트
#     audio = pyaudio.PyAudio()
#
#     try:
#         stream = audio.open(format=sample_format,
#                             channels=channels,
#                             rate=rate,
#                             input=True,
#                             frames_per_buffer=chunk)
#     except Exception as e:
#         print(f"Error opening audio stream: {e}")
#         return
#
#     frames = []
#
#     while is_recording:
#         try:
#             data = stream.read(chunk, exception_on_overflow=False)
#             frames.append(data)
#         except Exception as e:
#             print(f"Error capturing audio: {e}")
#             break
#
#     stream.stop_stream()
#     stream.close()
#     audio.terminate()
#
#     # WAV 파일 저장
#     wf = wave.open(audio_filename_wav, "wb")
#     wf.setnchannels(channels)
#     wf.setsampwidth(audio.get_sample_size(sample_format))
#     wf.setframerate(rate)
#     wf.writeframes(b"".join(frames))
#     wf.close()
#
#     # WAV -> MP3 변환
#     try:
#         sound = AudioSegment.from_wav(audio_filename_wav)
#         sound.export(audio_filename_mp3, format="mp3")
#         print(f"Audio saved to {audio_filename_mp3}")
#         os.remove(audio_filename_wav)  # WAV 파일 삭제 (선택)
#     except Exception as e:
#         print(f"Error converting audio to MP3: {e}")
#
# # WebSocket 엔드포인트
# # WebSocket 엔드포인트
# # @router.websocket("/record")
# # async def record_endpoint(websocket: WebSocket):
# #     global is_recording
# #     await websocket.accept()
# #
# #     # WebSocket에서 uuid, intro_no, round_id 받기
# #     data = await websocket.receive_json()
# #     uuid = data.get("uuid")
# #     intro_no = data.get("intro_no")
# #     round_id = data.get("round_id")
# #
# #     if not all([uuid, intro_no, round_id]):
# #         await websocket.send_text("Missing required parameters (uuid, intro_no, round_id).")
# #         await websocket.close()
# #         return
#
#     # 폴더 생성
#     # folder_path = create_directory(uuid, intro_no, round_id)
#
#     # 녹화 및 녹음 시작
#     is_recording = True
#     video_thread = threading.Thread(target=record_video, args=(folder_path,))
#     audio_thread = threading.Thread(target=record_audio, args=(folder_path,))
#     video_thread.start()
#     audio_thread.start()
#
#     # 반복 횟수 설정
#     total_duration = 2 * (20 + 40)  # 2번 반복 테스트
#     # total_duration = 8 * (20 + 40)  # 8번 반복용 (주석처리)
#
#     time.sleep(total_duration)  # 잘못된 들여쓰기 수정됨
#
#     # 녹화 및 녹음 종료
#     is_recording = False
#     video_thread.join()
#     audio_thread.join()
#
#     # await websocket.send_text(f"Recording and audio capturing finished! Files saved to {folder_path}")
#     # await websocket.close()
#
#
# # =========================================================
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

def save_interview_to_db(uuid, intro_no, round_id):
    """Oracle DB에 인터뷰 데이터를 저장하는 함수"""
    connection = get_oracle_connection()
    if not connection:
        print("Failed to connect to the database.")
        return False

    try:
        cursor = connection.cursor()
        insert_query = """
        INSERT INTO INTERVIEW (INT_ID, INTRO_NO, INT_DATE, INTERVIEW_ROUND, INT_IS_DELETED)
        VALUES (:uuid, :intro_no, SYSDATE, :round_id, 'N')
        """
        cursor.execute(insert_query, {
            "uuid": uuid,
            "intro_no": intro_no,
            "round_id": round_id
        })
        connection.commit()
        print(f"Successfully saved interview with ID {uuid}")
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

# 녹화 시작 엔드포인트
@router.post("/record/start")
def start_recording(uuid: str, intro_no: str, round_id: str):
    global is_recording

    with recording_lock:
        if is_recording:
            raise HTTPException(status_code=400, detail="Recording is already in progress.")

        # DB에 인터뷰 데이터 저장
        if not save_interview_to_db(uuid, intro_no, round_id):
            raise HTTPException(status_code=500, detail="Failed to save interview to the database.")

        create_directory()
        audio_filename_wav = os.path.join(AUDIO_PATH, f"{uuid}_{intro_no}_interview_{round_id}.wav")
        audio_filename_mp3 = os.path.join(AUDIO_PATH, f"{uuid}_{intro_no}_interview_{round_id}.mp3")
        video_filename = os.path.join(VIDEO_PATH, f"{uuid}_{intro_no}_interview_{round_id}.mp4")

        # 녹화 및 녹음 시작
        is_recording = True
        video_thread = threading.Thread(target=stream_and_record_video, args=(video_filename,))
        audio_thread = threading.Thread(target=record_audio, args=(audio_filename_wav, audio_filename_mp3))
        video_thread.start()
        audio_thread.start()

    return JSONResponse(content={"message": "Recording started.", "uuid": uuid})

# 녹화 중지 엔드포인트
@router.post("/record/stop")
def stop_recording():
    global is_recording

    with recording_lock:
        if not is_recording:
            raise HTTPException(status_code=400, detail="No recording is in progress.")

        is_recording = False  # 녹화를 중단

    return JSONResponse(content={"message": "Recording stopped."})
# # # ===========================================================
# from fastapi import APIRouter, HTTPException, BackgroundTasks
# from fastapi.responses import JSONResponse
# import cv2
# import pyaudio
# import wave
# import threading
# import time
# import os
#
# from numpy import number
# from pydub import AudioSegment
#
# router = APIRouter()
#
# # 전역 변수
# is_recording = False
# recording_threads = []
#
# # 경로 설정
# BASE_PATH = "C:/JOBISIMG"
# AUDIO_PATH = os.path.join(BASE_PATH, "audio")
# VIDEO_PATH = os.path.join(BASE_PATH, "video")
#
# # 폴더 생성 함수
# def create_directory():
#     if not os.path.exists(BASE_PATH):
#         os.makedirs(BASE_PATH, exist_ok=True)
#     if not os.path.exists(AUDIO_PATH):
#         os.makedirs(AUDIO_PATH, exist_ok=True)
#     if not os.path.exists(VIDEO_PATH):
#         os.makedirs(VIDEO_PATH, exist_ok=True)
#
# # 카메라 스트리밍 및 녹화 함수
# def stream_and_record_video(video_filename, duration):
#     global is_recording
#
#     try:
#         cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
#         cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
#         cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
#         cap.set(cv2.CAP_PROP_FPS, 20)
#
#         if not cap.isOpened():
#             raise RuntimeError("Failed to open the camera.")
#
#         fourcc = cv2.VideoWriter_fourcc(*"mp4v")
#         out = cv2.VideoWriter(video_filename, fourcc, 20.0, (640, 480))
#
#         start_time = time.time()
#         while is_recording and (time.time() - start_time < duration):
#             ret, frame = cap.read()
#             if not ret:
#                 break
#
#             frame = cv2.flip(frame, 1)
#             out.write(frame)
#
#         cap.release()
#         out.release()
#     except RuntimeError as e:
#         print(f"Video recording error: {e}")
#
# # 오디오 녹음 함수
# def record_audio(audio_filename_wav, audio_filename_mp3, duration):
#     global is_recording
#
#     chunk = 1024
#     sample_format = pyaudio.paInt16
#     channels = 1
#     rate = 44100
#     audio = pyaudio.PyAudio()
#
#     try:
#         stream = audio.open(format=sample_format,
#                             channels=channels,
#                             rate=rate,
#                             input=True,
#                             frames_per_buffer=chunk)
#
#         frames = []
#         start_time = time.time()
#
#         while is_recording and (time.time() - start_time < duration):
#             data = stream.read(chunk, exception_on_overflow=False)
#             frames.append(data)
#
#         stream.stop_stream()
#         stream.close()
#         audio.terminate()
#
#         wf = wave.open(audio_filename_wav, "wb")
#         wf.setnchannels(channels)
#         wf.setsampwidth(audio.get_sample_size(sample_format))
#         wf.setframerate(rate)
#         wf.writeframes(b"".join(frames))
#         wf.close()
#
#         sound = AudioSegment.from_wav(audio_filename_wav)
#         sound.export(audio_filename_mp3, format="mp3")
#         os.remove(audio_filename_wav)
#     except Exception as e:
#         print(f"Audio recording error: {e}")
#
# @router.post("/record/start")
# def start_recording(uuid: str, int_id: str, intro_no: int, interview_round: int, duration: int = 120):
#     global is_recording, recording_threads
#
#     if is_recording:
#         raise HTTPException(status_code=400, detail="Recording is already in progress.")
#
#     create_directory()
#
#     audio_filename_wav = os.path.join(AUDIO_PATH, f"{uuid}_{int_id}_{intro_no}_{interview_round}.wav")
#     audio_filename_mp3 = os.path.join(AUDIO_PATH, f"{uuid}_{int_id}_{intro_no}_{interview_round}.mp3")
#     video_filename = os.path.join(VIDEO_PATH, f"{uuid}_{int_id}_{intro_no}_{interview_round}.mp4")
#
#     is_recording = True
#
#     video_thread = threading.Thread(target=stream_and_record_video, args=(video_filename, duration))
#     audio_thread = threading.Thread(target=record_audio, args=(audio_filename_wav, audio_filename_mp3, duration))
#
#     video_thread.start()
#     audio_thread.start()
#
#     recording_threads = [video_thread, audio_thread]
#
#     return JSONResponse(content={"message": "Recording started."})
#
#
# @router.post("/record/stop")
# def stop_recording():
#     global is_recording, recording_threads
#
#     if not is_recording:
#         raise HTTPException(status_code=400, detail="No recording in progress.")
#
#     is_recording = False
#
#     for thread in recording_threads:
#         thread.join()
#
#     recording_threads = []
#     return JSONResponse(content={"message": "Recording stopped."})


# from fastapi import APIRouter, BackgroundTasks
# from pydantic import BaseModel
# import os
# import uuid
# import cv2
# import pyaudio
# import wave
# from datetime import datetime
# from pydub import AudioSegment
#
# router = APIRouter()
#
#
# # 디렉토리 생성 함수
# def create_directories():
#     base_path = "C:\\JOBISIMG"
#     video_path = os.path.join(base_path, "video")
#     audio_path = os.path.join(base_path, "audio")
#
#     if not os.path.exists(base_path):
#         os.makedirs(base_path)
#     if not os.path.exists(video_path):
#         os.makedirs(video_path)
#     if not os.path.exists(audio_path):
#         os.makedirs(audio_path)
#
#     return video_path, audio_path
#
#
# # 파일명 생성 함수
# def generate_filename(base_path, intro_no, interview_round, ext):
#     filename = f"{uuid.uuid4()}_{intro_no}_{interview_round}.{ext}"
#     full_path = os.path.join(base_path, filename)
#
#     count = 1
#     while os.path.exists(full_path):
#         filename = f"{uuid.uuid4()}_{intro_no}_{interview_round}({count}).{ext}"
#         full_path = os.path.join(base_path, filename)
#         count += 1
#
#     return full_path
#
#
# # 비디오와 오디오 녹화 작업
# def record_video_audio(intro_no, interview_round, duration):
#     video_path, audio_path = create_directories()
#
#     # 비디오 녹화 파일 경로
#     video_file = generate_filename(video_path, intro_no, interview_round, "mp4")
#
#     # 오디오 녹음 파일 경로
#     audio_file = generate_filename(audio_path, intro_no, interview_round, "mp3")
#
#     # 비디오 녹화 설정
#     cap = cv2.VideoCapture(0)
#     fourcc = cv2.VideoWriter_fourcc(*"mp4v")
#     fps = 20
#     frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#     frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#     out = cv2.VideoWriter(video_file, fourcc, fps, (frame_width, frame_height))
#
#     # 오디오 녹음 설정
#     audio_format = pyaudio.paInt16
#     channels = 1
#     rate = 44100
#     chunk = 1024
#     audio = pyaudio.PyAudio()
#     stream = audio.open(format=audio_format, channels=channels, rate=rate, input=True, frames_per_buffer=chunk)
#
#     frames = []
#
#     try:
#         start_time = datetime.now()
#         while (datetime.now() - start_time).seconds < duration:
#             ret, frame = cap.read()
#             if ret:
#                 out.write(frame)
#
#             data = stream.read(chunk)
#             frames.append(data)
#
#         # 비디오 녹화 종료
#         cap.release()
#         out.release()
#
#         # 오디오 녹음 종료
#         stream.stop_stream()
#         stream.close()
#         audio.terminate()
#
#         # WAV로 저장 후 MP3 변환
#         temp_audio_file = audio_file.replace(".mp3", ".wav")
#         with wave.open(temp_audio_file, 'wb') as wf:
#             wf.setnchannels(channels)
#             wf.setsampwidth(audio.get_sample_size(audio_format))
#             wf.setframerate(rate)
#             wf.writeframes(b''.join(frames))
#
#         AudioSegment.from_wav(temp_audio_file).export(audio_file, format="mp3")
#         os.remove(temp_audio_file)
#
#     except Exception as e:
#         print(f"Error during recording: {e}")
#     finally:
#         if cap.isOpened():
#             cap.release()
#         if out:
#             out.release()
#         if stream:
#             stream.stop_stream()
#             stream.close()
#         audio.terminate()
#
#     return video_file, audio_file
# class RecordingRequest(BaseModel):
#     intro_no: str  # 필수
#     interview_round: int  # 필수
#     duration: int = 20  # 선택, 기본값 20초
#
#
# # HTTP API 엔드포인트
# @router.post("/start-recording")
# async def start_recording(background_tasks: BackgroundTasks, intro_no: str, interview_round: int, duration: int = 20):
#     # 백그라운드 작업으로 녹화/녹음 수행
#     print(f"Received request: {request}")
#
#     # 녹화/녹음 작업 추가
#     background_tasks.add_task(
#         record_video_audio,
#         request.intro_no,
#         request.interview_round,
#         request.duration
#     )
#     background_tasks.add_task(record_video_audio, intro_no, interview_round, duration)
#     return {"message": "Recording started in the background."}
