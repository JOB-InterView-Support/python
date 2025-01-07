from fastapi import APIRouter, UploadFile, Form, HTTPException
from pydantic import BaseModel
import os
import uuid
from google.cloud import speech
from google.cloud.speech import RecognitionConfig, RecognitionAudio
import wave
from pydub import AudioSegment
import logging
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text


# 라우터 설정
router = APIRouter()

BASE_PATH = "C:/JOBISIMG"
AUDIO_PATH = os.path.join(BASE_PATH, "AUDIO")
Text_Path = os.path.join(BASE_PATH, "TEXT")

# 폴더 생성
os.makedirs(AUDIO_PATH, exist_ok=True)
os.makedirs(Text_Path, exist_ok=True)

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)

# 데이터베이스 URL
DATABASE_URL = "oracle+cx_oracle://C##SS:1234@ktj0514.synology.me:1521/xe"  # 예시 (실제 DB에 맞게 수정)

# 엔진 생성
engine = create_engine(DATABASE_URL, echo=True)

# 세션 로컬 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Google API 환경 변수 확인
google_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if not google_credentials_path:
    raise HTTPException(status_code=500, detail="Google Cloud 인증 정보가 설정되지 않았습니다.")

# 데이터 모델 정의
class VoiceTranscriptionRequest(BaseModel):
    language_code: str = "ko-KR"  # 기본 언어는 한국어

class VoiceTranscriptionResponse(BaseModel):
    transcription: str  # 변환된 텍스트

# STT API 엔드포인트
@router.post("/stt", response_model=VoiceTranscriptionResponse)
async def stt(audio_id: str, int_id: str, language_code: str = Form("ko-KR")):
    """
    음성 파일 ID(AUDIO_ID)와 면접 ID(INT_ID)를 받아 Google Speech-to-Text로 텍스트 변환.
    """
    try:
        # INTERVIEW_AUDIO에서 해당 AUDIO_ID와 INT_ID를 통해 음성 파일 경로 조회
        audio_path = get_audio_path_from_db(audio_id, int_id)

        if not audio_path:
            raise HTTPException(status_code=404, detail="해당 음성 파일을 찾을 수 없습니다.")

        # 음성 파일 경로에서 음성 파일을 다운로드하여 변환
        transcription = await transcribe_audio_async(audio_path, language_code)

        # SQL 쿼리를 사용하여 변환된 텍스트와 관련 데이터를 DB에 저장
        save_to_database_with_query(
            audio_id=audio_id,
            transcription=transcription,
            status="COMPLETED",
            extext="예제 텍스트입니다."  # 예제 텍스트, 필요시 변경
        )

        return {"transcription": transcription}

    except Exception as e:
        logging.error(f"변환 중 오류가 발생했습니다: {str(e)}")
        raise HTTPException(status_code=500, detail=f"변환 중 오류가 발생했습니다: {str(e)}")

#음성 테이블 조회 디비 저장
def get_audio_path_from_db(audio_id: str, int_id: str) -> str:
    """
    INTERVIEW_AUDIO 테이블에서 AUDIO_ID와 INT_ID에 해당하는 음성 파일 경로를 조회.
    """
    session = SessionLocal()

    try:
        query = text("""
            SELECT AUDIO_PATH
            FROM INTERVIEW_AUDIO
            WHERE AUDIO_ID = :audio_id AND INT_ID = :int_id
        """)

        result = session.execute(query, {"audio_id": audio_id, "int_id": int_id}).fetchone()

        if result:
            return result[0]  # 음성 파일 경로 반환
        else:
            return None

    except Exception as e:
        logging.error(f"DB 조회 중 오류가 발생했습니다: {str(e)}")
        raise HTTPException(status_code=500, detail="DB 조회 중 오류가 발생했습니다.")
    finally:
        session.close()

# 파일 저장 함수
async def save_audio_file(file: UploadFile, upload_dir: str = AUDIO_PATH) -> str:
    """
    업로드된 음성 파일을 지정된 경로에 저장.
    """
    os.makedirs(upload_dir, exist_ok=True)

    if not file.filename.endswith(".wav"):
        logging.error("지원되지 않는 파일 형식입니다. WAV 파일만 업로드하세요.")
        raise HTTPException(status_code=400, detail="지원되지 않는 파일 형식입니다. WAV 파일만 업로드하세요.")

    unique_filename = f"{uuid.uuid4()}.wav"
    file_path = os.path.join(upload_dir, unique_filename)

    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        logging.info(f"음성 파일이 성공적으로 저장되었습니다: {file_path}")
    except Exception as e:
        logging.error(f"파일 저장 중 오류가 발생했습니다: {str(e)}")
        raise HTTPException(status_code=500, detail=f"파일 저장 중 오류가 발생했습니다: {str(e)}")

    return file_path

# 텍스트 저장 함수
def save_transcription(transcription: str) -> None:
    """
    변환된 텍스트를 파일로 저장.
    """
    unique_filename = f"{uuid.uuid4()}.txt"
    text_file_path = os.path.join(Text_Path, unique_filename)

    try:
        with open(text_file_path, "w", encoding="utf-8") as text_file:
            text_file.write(transcription)
        logging.info(f"변환된 텍스트가 성공적으로 저장되었습니다: {text_file_path}")
    except Exception as e:
        logging.error(f"텍스트 저장 중 오류가 발생했습니다: {str(e)}")
        raise HTTPException(status_code=500, detail="텍스트 저장 중 오류가 발생했습니다.")

# 파일을 모노로 변환하는 함수
def convert_to_mono(file_path: str) -> str:
    """
    WAV 파일을 모노 채널로 변환.
    """
    try:
        audio = AudioSegment.from_wav(file_path)
        if audio.channels != 1:
            mono_file_path = file_path.replace(".wav", "_mono.wav")
            audio = audio.set_channels(1)
            audio.export(mono_file_path, format="wav")
            logging.info(f"모노 변환 완료: {mono_file_path}")
            return mono_file_path
        else:
            logging.info("이미 모노 오디오입니다.")
            return file_path
    except Exception as e:
        logging.error(f"모노 변환 중 오류가 발생했습니다: {str(e)}")
        raise HTTPException(status_code=500, detail="모노 변환 중 오류가 발생했습니다.")

# Google Speech-to-Text 변환 함수
async def transcribe_audio_async(file_path: str, language_code: str = "ko-KR") -> str:
    """
    Google Speech-to-Text를 사용해 음성을 텍스트로 변환.
    """
    client = speech.SpeechClient()

    try:
        mono_file_path = convert_to_mono(file_path)

        with open(mono_file_path, "rb") as audio_file:
            content = audio_file.read()

        audio = RecognitionAudio(content=content)

        with wave.open(mono_file_path, 'rb') as wave_file:
            sample_rate = wave_file.getframerate()

        config = RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=sample_rate,
            language_code=language_code,
        )

        operation = client.long_running_recognize(config=config, audio=audio)
        logging.info(f"음성 인식 시작: {mono_file_path}")
        response = operation.result()

        transcription = " ".join(result.alternatives[0].transcript for result in response.results)
        logging.info(f"변환된 텍스트: {transcription}")
        return transcription.strip()

    except Exception as e:
        logging.error(f"음성 변환 중 오류가 발생했습니다: {str(e)}")
        raise HTTPException(status_code=500, detail=f"음성 변환 중 오류가 발생했습니다: {str(e)}")

def save_to_database_with_query(audio_id: str, transcription: str, status: str = "COMPLETED", extext: str = ""):
    """
    SQL 쿼리를 사용하여 변환된 텍스트를 DB에 저장.
    """
    session = SessionLocal()
    stt_id = str(uuid.uuid4())  # STT ID 생성
    stt_created = datetime.datetime.utcnow()
    stt_completed = datetime.datetime.utcnow()

    query = text("""
        INSERT INTO INTERVIEW_STT (STT_ID, AUDIO_ID, STT_TEXT, STT_STATUS, STT_CREATED, STT_COMPLETED, STT_EXTEXT, STT_EDIT_TEXT)
        VALUES (:stt_id, :audio_id, :stt_text, :stt_status, :stt_created, :stt_completed, :stt_extext, :stt_edit_text)
    """)

    try:
        session.execute(query, {
            "stt_id": stt_id,
            "audio_id": audio_id,
            "stt_text": transcription,
            "stt_status": status,
            "stt_created": stt_created,
            "stt_completed": stt_completed,
            "stt_extext": extext,
            "stt_edit_text": None  # 수정된 텍스트는 처음엔 NULL
        })
        session.commit()
        logging.info(f"STT 데이터가 성공적으로 저장되었습니다: STT_ID={stt_id}")
    except Exception as e:
        session.rollback()
        logging.error(f"DB 저장 중 오류가 발생했습니다: {str(e)}")
        raise HTTPException(status_code=500, detail="DB 저장 중 오류가 발생했습니다.")
    finally:
        session.close()

def update_stt_status(stt_id: str, new_status: str, edit_text: str = None):
    """
    STT 상태 또는 수정된 텍스트 업데이트.
    """
    session = SessionLocal()

    query = text("""
        UPDATE INTERVIEW_STT
        SET STT_STATUS = :new_status,
            STT_EDIT_TEXT = :edit_text,
            STT_COMPLETED = :completed_time
        WHERE STT_ID = :stt_id
    """)

    try:
        session.execute(query, {
            "stt_id": stt_id,
            "new_status": new_status,
            "edit_text": edit_text,
            "completed_time": datetime.datetime.utcnow()
        })
        session.commit()
        logging.info(f"STT 데이터가 성공적으로 업데이트되었습니다: STT_ID={stt_id}")
    except Exception as e:
        session.rollback()
        logging.error(f"DB 업데이트 중 오류가 발생했습니다: {str(e)}")
        raise HTTPException(status_code=500, detail="DB 업데이트 중 오류가 발생했습니다.")
    finally:
        session.close()