from pydantic import BaseModel
import cv2
import os
import pyaudio
import wave
import threading
from fastapi.responses import JSONResponse
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from app.utils.db_connection import get_oracle_connection
import random
import textwrap  # 줄바꿈 처리를 위한 모듈 추가
from typing import Optional

router = APIRouter()

# OpenCV 카메라 초기화
camera = cv2.VideoCapture(0)

# 카운트다운 상태 및 단계
current_countdown = 0
countdown_stage = "none"
is_countdown_active = False
is_recording = False  # 녹화/녹음 상태 플래그

# 카운트다운 초기 값
initial_countdown = 3
question_countdown = 3
answer_countdown = 3

# 저장 경로
BASE_DIR = "C:/JOBISIMG"
VIDEO_DIR = os.path.join(BASE_DIR, "VIDEO")
AUDIO_DIR = os.path.join(BASE_DIR, "AUDIO")
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)




def record_video(file_path):
    """영상 녹화 함수"""
    global is_recording
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(file_path, fourcc, 20.0, (640, 480))

    while is_recording:
        success, frame = camera.read()
        if not success:
            break
        flipped_frame = cv2.flip(frame, 1)
        out.write(flipped_frame)

    out.release()
    print(f"영상 녹화 저장 완료: {file_path}")


def record_audio(file_path):
    """음성 녹음 함수"""
    global is_recording
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
    frames = []

    while is_recording:
        data = stream.read(1024)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    audio.terminate()

    # WAV 파일 저장
    wav_file = file_path.replace(".mp3", ".wav")
    with wave.open(wav_file, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(44100)
        wf.writeframes(b"".join(frames))
    print(f"음성 WAV 파일 저장 완료: {wav_file}")

    # WAV 파일을 MP3로 변환
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_wav(wav_file)
        audio.export(file_path, format="mp3")
        os.remove(wav_file)
        print(f"음성 MP3 파일 저장 완료: {file_path}")
    except ImportError:
        print("pydub 라이브러리가 설치되지 않아 WAV 파일을 MP3로 변환하지 못했습니다.")


current_question_index = 0  # 진행 중인 질문 인덱스

def start_countdown(uuid, int_id, round_id):
    global current_countdown, countdown_stage, is_countdown_active, is_recording, current_question_index
    global interviewState, filename

    # 녹화 및 녹음 파일 경로
    video_file = os.path.join(VIDEO_DIR, f"{uuid}_{int_id}_{round_id}.mp4")
    audio_file = os.path.join(AUDIO_DIR, f"{uuid}_{int_id}_{round_id}.mp3")

    # 녹화 및 녹음 시작
    is_recording = True
    video_thread = threading.Thread(target=record_video, args=(video_file,))
    audio_thread = threading.Thread(target=record_audio, args=(audio_file,))
    video_thread.start()
    audio_thread.start()

    # 초기 카운트다운
    countdown_stage = "initial"
    current_countdown = initial_countdown
    while current_countdown > 0:
        time.sleep(1)
        current_countdown -= 1

    # 질문-답변 반복 단계
    all_questions = selected_questions + question_set_questions
    for i, question in enumerate(all_questions):
        current_question_index = i

        # 질문 카운트다운
        countdown_stage = "question"
        current_countdown = question_countdown
        while current_countdown > 0:
            time.sleep(1)
            current_countdown -= 1

        # 답변 카운트다운
        countdown_stage = "answer"
        current_countdown = answer_countdown
        while current_countdown > 0:
            time.sleep(1)
            current_countdown -= 1

    # 녹화 및 녹음 종료
    countdown_stage = "finished"
    is_recording = False
    video_thread.join()
    audio_thread.join()
    is_countdown_active = False

    # 데이터베이스에 AUDIO 및 VIDEO 레코드 삽입
    audio_filename = os.path.basename(audio_file)  # 오디오 파일명 추출
    video_filename = os.path.basename(video_file)  # 비디오 파일명 추출
    insert_audio_record(InterviewRequest(uuid=uuid, intro_no=None, round_id=round_id, int_id=int_id), audio_filename)
    insert_video_record(InterviewRequest(uuid=uuid, intro_no=None, round_id=round_id, int_id=int_id), video_filename)

    # 전역 변수 업데이트
    filename = {"audio": audio_filename, "video": video_filename}  # 파일명 저장
    interviewState = True  # 상태 변경

    print("모든 질문과 답변이 완료되었습니다!")





def generate_frames():
    """카메라 프레임 생성 및 카운트다운 텍스트 표시"""
    global current_countdown, countdown_stage, current_question_index

    while True:
        success, frame = camera.read()
        if not success:
            break

        flipped_frame = cv2.flip(frame, 1)
        frame_pil = Image.fromarray(cv2.cvtColor(flipped_frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(frame_pil)
        font_path = "C:/Windows/Fonts/malgun.ttf"
        font_common = ImageFont.truetype(font_path, 30)

        wrapped_message = []  # wrapped_message 초기화

        # 화면 중앙에 빨간색 십자가 그리기
        frame_width = frame_pil.width
        frame_height = frame_pil.height
        cross_size = 10  # 십자가 크기
        cross_color = (255, 0, 0)  # 빨간색

        # 십자가 중심 좌표 계산
        center_x = frame_width // 2
        center_y = frame_height // 2

        # 십자가 그리기
        draw.line(
            [(center_x - cross_size, center_y), (center_x + cross_size, center_y)],
            fill=cross_color,
            width=2,
        )
        draw.line(
            [(center_x, center_y - cross_size), (center_x, center_y + cross_size)],
            fill=cross_color,
            width=2,
        )

        if countdown_stage in ["initial", "question", "answer"]:
            if countdown_stage == "initial":
                message = "5초 후에 시작합니다!"
                color = (255, 0, 0)  # 빨간색
                wrapped_message = textwrap.wrap(message, width=20)
            elif countdown_stage == "question" and current_question_index < len(selected_questions + question_set_questions):
                # 현재 질문이 유효한 경우
                all_questions = selected_questions + question_set_questions
                message = all_questions[current_question_index]
                color = (0, 0, 255)  # 파란색
                wrapped_message = textwrap.wrap(message, width=20)
            elif countdown_stage == "answer":
                message = "답변 시간:"
                color = (0, 255, 0)  # 초록색
                wrapped_message = textwrap.wrap(message, width=20)
            else:
                # 질문이 끝난 경우
                message = "모든 질문이 완료되었습니다."
                color = (0, 255, 255)  # 노란색
                wrapped_message = textwrap.wrap(message, width=20)

            # 메시지 텍스트 그리기
            text_y = 5  # 텍스트의 상단 기준 Y 좌표
            padding = 8  # 배경 사각형의 여백

            for line in wrapped_message:
                # 텍스트의 너비와 높이를 계산
                bbox = draw.textbbox((0, 0), line, font=font_common)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

                # 텍스트의 X 좌표와 Y 좌표 계산
                text_x = (frame_pil.width - text_width) // 2  # 이미지 너비의 중앙에 정렬

                # 배경 사각형 좌표 계산
                rect_x1 = text_x - padding
                rect_y1 = text_y - padding
                rect_x2 = text_x + text_width + padding
                rect_y2 = text_y + text_height + padding

                # 흰색 배경 사각형 그리기
                draw.rectangle([rect_x1, rect_y1, rect_x2, rect_y2], fill=(255, 255, 255))

                # 텍스트 그리기
                draw.text((text_x, text_y), line, font=font_common, fill=(0, 0, 0))

                # 줄 간격 조정
                text_y += text_height + 2 * padding

            # 카운트다운 텍스트 그리기
            countdown_text = str(current_countdown)
            if wrapped_message:
                bbox_last_line = draw.textbbox((0, 0), wrapped_message[-1], font=font_common)
                countdown_x = (frame_pil.width + bbox_last_line[2]) // 2 + 20  # 마지막 줄 오른쪽에 위치
                countdown_y = text_y - 40  # 마지막 줄과 같은 높이
                draw.text((countdown_x, countdown_y), countdown_text, font=font_common, fill=color)

        frame = cv2.cvtColor(np.array(frame_pil), cv2.COLOR_RGB2BGR)
        _, buffer = cv2.imencode(".jpg", frame)
        frame_bytes = buffer.tobytes()
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"

@router.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


class InterviewRequest(BaseModel):
    uuid: str
    intro_no: Optional[str]  # None을 허용
    round_id: str
    int_id: str





def insert_audio_record(request: InterviewRequest, audio_filename: str):
    """
    INTERVIEW_AUDIO 테이블에 새로운 레 코드를 삽입합니다.

    :param request: InterviewRequest 객체
    :param audio_filename: 저장된 MP3 파일 이름
    """
    try:
        # Oracle DB 연결
        connection = get_oracle_connection()
        if not connection:
            print("Database connection failed")
            return

        cursor = connection.cursor()

        # AUDIO_ID 생성
        audio_id = f"{request.uuid}_audio_{request.round_id}"

        # AUDIO_PATH 생성
        audio_path = f"C:/JOBISIMG/AUDIO/{audio_filename}"

        # INSERT 쿼리 작성
        insert_query = """
        INSERT INTO INTERVIEW_AUDIO (AUDIO_ID, INT_ID, AUDIO_PATH)
        VALUES (:audio_id, :int_id, :audio_path)
        """
        cursor.execute(insert_query, {
            "audio_id": audio_id,
            "int_id": request.int_id,
            "audio_path": audio_path
        })

        # 트랜잭션 커밋
        connection.commit()
        print(f"INTERVIEW_AUDIO 테이블에 레코드 삽입 완료: AUDIO_ID={audio_id}")

    except Exception as e:
        print(f"데이터베이스 INSERT 중 오류 발생: {e}")
    finally:
        # 연결 닫기
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def insert_video_record(request: InterviewRequest, video_filename: str):
    """
    INTERVIEW_VIDEO 테이블에 새로운 레코드를 삽입합니다.

    :param request: InterviewRequest 객체
    :param video_filename: 저장된 MP4 파일 이름
    """
    try:
        # Oracle DB 연결
        connection = get_oracle_connection()
        if not connection:
            print("Database connection failed")
            return

        cursor = connection.cursor()

        # IV_ID 생성
        iv_id = f"{request.uuid}_video_{request.round_id}"

        # IV_PATH 생성
        iv_path = f"C:/JOBISIMG/VIDEO/{video_filename}"

        # INSERT 쿼리 작성
        insert_query = """
        INSERT INTO INTERVIEW_VIDEO (IV_ID, INT_ID, IV_PATH)
        VALUES (:iv_id, :int_id, :iv_path)
        """
        cursor.execute(insert_query, {
            "iv_id": iv_id,
            "int_id": request.int_id,
            "iv_path": iv_path
        })

        # 트랜잭션 커밋
        connection.commit()
        print(f"INTERVIEW_VIDEO 테이블에 레코드 삽입 완료: IV_ID={iv_id}")

    except Exception as e:
        print(f"데이터베이스 INSERT 중 오류 발생: {e}")
    finally:
        # 연결 닫기
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# 공통 질문 전역 변수
common_questions = []
selected_questions = []  # 랜덤으로 뽑은 질문을 저장하는 변수
question_set_questions = []  # 추가로 가져온 질문 저장

intro_no = None  # INTERVIEW_REQUEST에서 intro_no 값
round_id = None  # INTERVIEW_REQUEST에서 round_id 값
int_id = None  # INTERVIEW_REQUEST에서 int_id 값

@router.post("/record/start")
async def start_recording(request: InterviewRequest):
    global is_countdown_active, common_questions, selected_questions, question_set_questions

    global intro_no, round_id, int_id  # 새로 추가된 전역 변수 사용 선언

    # 전역 변수 값 설정
    intro_no = request.intro_no
    round_id = request.round_id
    int_id = request.int_id

    # 카운트다운 진행 상태 확인
    if not is_countdown_active:
        is_countdown_active = True

        # DB에서 질문 가져오기
        try:
            # Oracle DB 연결
            connection = get_oracle_connection()
            if not connection:
                return JSONResponse(status_code=500, content={"message": "Database connection failed"})

            cursor = connection.cursor()

            # 첫 번째 쿼리: 공통 질문 가져오기
            query_common = """
            SELECT QUE_TITLE
            FROM INTERVIEW_QUESTIONS
            WHERE QUE_USE_STATUS = 'Y'
            """
            cursor.execute(query_common)
            common_questions = [row[0] for row in cursor.fetchall()]

            # 랜덤으로 3개의 질문 선택
            if len(common_questions) >= 3:
                selected_questions = random.sample(common_questions, 3)
            else:
                selected_questions = common_questions  # 질문 개수가 3개 미만인 경우 모두 선택

            # 두 번째 쿼리: INTERVIEW_QUESTION_SET에서 데이터 가져오기
            query_question_set = """
            SELECT INTERVIEW_QUESTIONS
            FROM INTERVIEW_QUESTION_SET
            WHERE INTRO_NO = :intro_no
            AND INTERVIEW_ROUND = :round_id
            """
            cursor.execute(query_question_set, {"intro_no": request.intro_no, "round_id": request.round_id})
            question_set_questions = [row[0] for row in cursor.fetchall()]

            cursor.close()
            connection.close()

            # 출력
            print("Common Questions:", common_questions)
            print("Selected Questions (Random 3):", selected_questions)
            print("Question Set Questions:", question_set_questions)

        except Exception as e:
            print(f"Error fetching questions from DB: {e}")
            return JSONResponse(status_code=500, content={"message": "Error fetching questions from DB"})

        # 카운트다운 스레드 시작
        threading.Thread(target=start_countdown, args=(request.uuid, request.int_id, request.round_id)).start()
        return JSONResponse(
            status_code=200,
            content={
                "message": "녹화 시작",
                "random_questions": selected_questions,  # 랜덤으로 뽑은 질문
                "question_set_questions": question_set_questions,  # 추가로 가져온 질문
            }
        )
    else:
        return JSONResponse(status_code=400, content={"message": "카운트다운이 이미 진행 중입니다."})

# 전역 변수 선언
interviewState = False  # 인터뷰 진행 상태 플래그
filename = None  # 저장된 파일 이름


@router.get("/state")
async def get_interview_state():
    """
    인터뷰 상태 및 파일명, intro_no, round_id, int_id를 반환합니다.
    """
    global interviewState, filename, intro_no, round_id, int_id

    return JSONResponse(
        status_code=200,
        content={
            "interviewState": interviewState,  # 인터뷰 상태 반환
            "filename": filename,  # 저장된 파일명 반환
            "intro_no": intro_no,  # INTERVIEW_REQUEST에서 받은 intro_no 값
            "round_id": round_id,  # INTERVIEW_REQUEST에서 받은 round_id 값
            "int_id": int_id,  # INTERVIEW_REQUEST에서 받은 int_id 값
        },
    )