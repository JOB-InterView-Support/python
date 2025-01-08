from fastapi import APIRouter, Form, HTTPException
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
DATABASE_URL = "oracle+cx_oracle://C##SS:1234@ktj0514.synology.me:1521/xe"

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

# MP3 파일을 WAV로 변환하는 함수
def convert_mp3_to_wav(mp3_path: str) -> str:
    """
    MP3 파일을 WAV 파일로 변환.
    """
    try:
        audio = AudioSegment.from_mp3(mp3_path)
        wav_path = mp3_path.replace(".mp3", ".wav")
        audio.export(wav_path, format="wav")
        logging.info(f"MP3 파일이 WAV로 변환되었습니다: {wav_path}")
        return wav_path
    except Exception as e:
        logging.error(f"MP3 변환 중 오류가 발생했습니다: {str(e)}")
        raise HTTPException(status_code=500, detail="MP3 변환 중 오류가 발생했습니다.")

# 음성 파일을 5초 건너뛰고 1분씩 분할
def split_audio(file_path: str, start_offset: int = 5, segment_duration: int = 60) -> list:
    """
    WAV 파일을 지정된 시작 지점부터 분할.
    """
    try:
        audio = AudioSegment.from_wav(file_path)
        duration_ms = len(audio)
        segments = []

        for start_ms in range(start_offset * 1000, duration_ms, segment_duration * 1000):
            end_ms = min(start_ms + segment_duration * 1000, duration_ms)
            segment = audio[start_ms:end_ms]

            segment_filename = f"{uuid.uuid4()}.wav"
            segment_path = os.path.join(AUDIO_PATH, segment_filename)
            segment.export(segment_path, format="wav")
            segments.append(segment_path)

        logging.info(f"파일이 {len(segments)}개로 분할되었습니다 (5초 제외).")
        return segments

    except Exception as e:
        logging.error(f"파일 분할 중 오류가 발생했습니다: {str(e)}")
        raise HTTPException(status_code=500, detail="파일 분할 중 오류가 발생했습니다.")

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

# 분할된 파일 개별 변환 및 저장
async def process_and_save_segments(segment_paths: list, audio_id: str, language_code: str = "ko-KR"):
    """
    분할된 파일을 변환하고 변환된 텍스트를 DB에 저장.
    """
    client = speech.SpeechClient()

    try:
        for idx, segment_path in enumerate(segment_paths):
            mono_file_path = convert_to_mono(segment_path)

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
            logging.info(f"분할 파일 텍스트 변환 완료: {segment_path}")

            save_to_stt_table(
                audio_id=audio_id,
                transcription=transcription.strip(),
                extext=f"Segment {idx + 1}"
            )

    except Exception as e:
        logging.error(f"파일 처리 중 오류가 발생했습니다: {str(e)}")
        raise HTTPException(status_code=500, detail=f"파일 처리 중 오류가 발생했습니다: {str(e)}")

# STT API 엔드포인트
@router.post("/stt", response_model=VoiceTranscriptionResponse)
async def stt(
    audio_id: str = Form(..., description="음성 파일 ID를 입력하세요."),
    int_id: str = Form(..., description="인터뷰 ID를 입력하세요."),
    language_code: str = Form("ko-KR", description="변환 언어 코드를 입력하세요. (기본값: 한국어)")
):
    """
    제공된 audio_id와 int_id를 사용해 음성을 텍스트로 변환하는 엔드포인트.
    """
    try:
        audio_path = get_audio_path_from_db(audio_id, int_id)

        if not audio_path:
            raise HTTPException(status_code=404, detail="해당 음성 파일을 찾을 수 없습니다.")

        # MP3 파일인지 확인 후 WAV로 변환
        if audio_path.endswith(".mp3"):
            audio_path = convert_mp3_to_wav(audio_path)

        segment_paths = split_audio(audio_path, start_offset=5, segment_duration=60)
        await process_and_save_segments(segment_paths, audio_id, language_code)

        return {"message": "STT 변환 및 저장 완료"}

    except HTTPException as e:
        logging.error(f"API 요청 처리 중 오류: {str(e)}")
        raise e

    except Exception as e:
        logging.error(f"시스템 오류: {str(e)}")
        raise HTTPException(status_code=500, detail="시스템 오류가 발생했습니다.")

# 부모 테이블에서 경로 조회
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
            return result[0]
        else:
            raise HTTPException(status_code=404, detail="해당 음성 파일을 찾을 수 없습니다.")
    except Exception as e:
        logging.error(f"DB 조회 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail="DB 조회 중 오류가 발생했습니다.")
    finally:
        session.close()

# 변환된 텍스트를 DB에 저장
def save_to_stt_table(audio_id: str, transcription: str, extext: str):
    """
    INTERVIEW_STT 테이블에 변환된 텍스트를 저장.
    """
    session = SessionLocal()
    stt_id = str(uuid.uuid4())
    stt_created = datetime.datetime.utcnow()
    stt_completed = datetime.datetime.utcnow()

    query = text("""
        INSERT INTO INTERVIEW_STT (
            STT_ID, AUDIO_ID, STT_TEXT, STT_STATUS, STT_CREATED, STT_COMPLETED, STT_EXTEXT, STT_EDIT_TEXT
        )
        VALUES (
            :stt_id, :audio_id, :stt_text, :stt_status, :stt_created, :stt_completed, :stt_extext, NULL
        )
    """)

    try:
        session.execute(query, {
            "stt_id": stt_id,
            "audio_id": audio_id,
            "stt_text": transcription,
            "stt_status": "COMPLETED",
            "stt_created": stt_created,
            "stt_completed": stt_completed,
            "stt_extext": extext
        })
        session.commit()
        logging.info(f"STT 데이터 저장 성공: STT_ID={stt_id}")
    except Exception as e:
        session.rollback()
        logging.error(f"DB 저장 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail="DB 저장 중 오류가 발생했습니다.")
    finally:
        session.close()