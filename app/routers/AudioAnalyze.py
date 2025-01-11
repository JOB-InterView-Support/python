import os
import logging
import zlib
from datetime import datetime
from fastapi import APIRouter, Form, HTTPException, FastAPI
from google.cloud import speech, storage
from pydub import AudioSegment
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

router = APIRouter()

# 데이터베이스 연결 설정
DATABASE_URL = "oracle+cx_oracle://C##SS:1234@ktj0514.synology.me:1521/xe"
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# GCS 버킷 이름
BUCKET_NAME = "project_jobis"

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)

# 디렉토리 확인 및 생성 함수
def ensure_directory_exists(directory: str):
    """
    디렉토리가 존재하지 않으면 생성합니다.
    :param directory: 디렉토리 경로
    """
    if not os.path.exists(directory):
        os.makedirs(directory)
        logging.info(f"디렉토리 생성 완료: {directory}")
    else:
        logging.info(f"디렉토리 확인 완료: {directory}")

# 부모 테이블에서 AUDIO_ID 조회
def get_audio_id_from_interview_audio(audio_filename: str, session) -> str:
    """
    INTERVIEW_AUDIO 테이블에서 AUDIO_ID를 조회합니다.
    :param audio_filename: 오디오 파일 이름
    :param session: 데이터베이스 세션
    :return: 조회된 AUDIO_ID
    """
    try:
        query = text("SELECT AUDIO_ID FROM INTERVIEW_AUDIO WHERE AUDIO_PATH LIKE :audio_path")
        result = session.execute(query, {"audio_path": f"%{audio_filename}%"}).fetchone()
        if result:
            logging.info(f"INTERVIEW_AUDIO에서 AUDIO_ID 조회 완료: {result[0]}")
            return result[0]
        else:
            raise HTTPException(status_code=404, detail="INTERVIEW_AUDIO 테이블에서 AUDIO_ID를 찾을 수 없습니다.")
    except Exception as e:
        logging.error(f"INTERVIEW_AUDIO 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail="INTERVIEW_AUDIO 조회 중 오류가 발생했습니다.")


# MP3를 WAV로 변환
def convert_mp3_to_wav(mp3_file_path: str, output_folder: str) -> str:
    try:
        ensure_directory_exists(output_folder)  # 디렉토리 확인 및 생성
        wav_file_path = os.path.join(output_folder, os.path.basename(mp3_file_path).replace(".mp3", ".wav"))
        audio = AudioSegment.from_file(mp3_file_path, format="mp3")
        audio.export(wav_file_path, format="wav", parameters=["-ar", "16000", "-ac", "1"])
        logging.info(f"MP3를 WAV로 변환 완료: {wav_file_path}")
        return wav_file_path
    except Exception as e:
        logging.error(f"MP3를 WAV로 변환 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail="MP3를 WAV로 변환하는 중 오류가 발생했습니다.")

# Google STT 호출 (GCS URI 사용)
def transcribe_audio_from_gcs(gcs_uri: str, language_code: str = "ko-KR") -> str:
    try:
        client = speech.SpeechClient()
        audio = speech.RecognitionAudio(uri=gcs_uri)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code,
        )
        logging.info(f"Google STT 호출 시작 - GCS URI: {gcs_uri}")
        operation = client.long_running_recognize(config=config, audio=audio)

        response = operation.result(timeout=300)
        transcription = " ".join(result.alternatives[0].transcript for result in response.results)
        logging.info(f"Google STT 호출 완료 - 변환된 텍스트: {transcription}")
        return transcription.strip()
    except Exception as e:
        logging.error(f"Google STT 호출 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Google STT 호출 중 오류 발생: {str(e)}")

# AUDIO_ID 생성 함수
def generate_audio_id(audio_filename: str) -> str:
    hashed_filename = zlib.crc32(audio_filename.encode("utf-8"))
    current_timestamp = datetime.now().strftime('%Y%m%d%H%M')
    return f"AUDIO_{hashed_filename}_{current_timestamp}"

# STT_ID 생성 함수
def generate_stt_id(audio_id: str) -> str:
    current_timestamp = datetime.now().strftime('%Y%m%d%H%M')
    hashed_audio_id = zlib.crc32(audio_id.encode("utf-8"))
    return f"STT_{hashed_audio_id}_{current_timestamp}"

# 변환된 텍스트를 DB와 로컬에 저장
def save_transcription(audio_id: str, transcription: str, text_folder: str, session) -> str:
    try:
        ensure_directory_exists(text_folder)  # 디렉토리 확인 및 생성
        stt_id = generate_stt_id(audio_id)
        if not os.path.exists(text_folder):
            os.makedirs(text_folder)

        text_file_path = os.path.join(text_folder, f"{stt_id}.txt")

        with open(text_file_path, "w", encoding="utf-8") as text_file:
            text_file.write(transcription)
        logging.info(f"텍스트 파일 저장 완료: {text_file_path}")

        query = text("""
            INSERT INTO INTERVIEW_STT (STT_ID, AUDIO_ID, STT_FILE_PATH)
            VALUES (:stt_id, :audio_id, :stt_file_path)
        """)
        session.execute(query, {
            "stt_id": stt_id,
            "audio_id": audio_id,
            "stt_file_path": text_file_path
        })
        session.commit()
        logging.info(f"DB 저장 완료: STT_ID={stt_id}, AUDIO_ID={audio_id}")
        return text_file_path
    except Exception as e:
        logging.error(f"DB 저장 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail="DB 저장 중 오류가 발생했습니다.")

# GCS에 파일 업로드
def upload_to_gcs(bucket_name: str, local_file_path: str, destination_blob_name: str) -> str:
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(local_file_path)
        gcs_uri = f"gs://{bucket_name}/{destination_blob_name}"
        logging.info(f"GCS 업로드 완료: {gcs_uri}")
        return gcs_uri
    except Exception as e:
        logging.error(f"GCS 업로드 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"GCS 업로드 중 오류 발생: {str(e)}")

# API 엔드포인트 정의
@router.post("/analysis")
async def analyze_audio(
        audioFilename: str = Form(...),
        audioFolder: str = Form("C:\\JOBISIMG\\AUDIO"),
        wavOutputFolder: str = Form("C:\\JOBISIMG\\AUDIO_WAV"),
        textFolder: str = Form("C:\\JOBISIMG\\TEXT"),
        language_code: str = Form("ko-KR"),
):
    print("오디오 분석 시작")
    try:
        # 1. 파일 경로 확인
        audio_path = os.path.join(audioFolder, audioFilename)
        if not os.path.exists(audio_path):
            raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {audio_path}")

        # 2. MP3를 WAV로 변환
        wav_path = convert_mp3_to_wav(audio_path, wavOutputFolder)

        # 3. GCS에 WAV 파일 업로드
        gcs_audio_uri = upload_to_gcs(BUCKET_NAME, wav_path, f"audio/{os.path.basename(wav_path)}")

        # 4. Google STT 호출 (GCS URI 사용)
        transcription = transcribe_audio_from_gcs(gcs_audio_uri, language_code)

        # 5. 변환된 텍스트를 로컬에 저장하고 DB에 경로 저장
        with SessionLocal() as session:
            # 부모 테이블에서 AUDIO_ID 조회
            audio_id = get_audio_id_from_interview_audio(audioFilename, session)

            # 텍스트 저장 및 DB 저장
            text_file_path = save_transcription(audio_id, transcription, textFolder, session)

        # 6. 로컬 파일 삭제
        os.remove(wav_path)
        logging.info(f"WAV 파일 삭제 완료: {wav_path}")

        # 결과 반환
        return {
            "status": "success",
            "transcription": transcription,
            "gcs_audio_uri": gcs_audio_uri,
            "text_file_path": text_file_path,
            "audio_id": audio_id
        }
    except HTTPException as e:
        logging.error(f"API 요청 처리 중 오류: {e.detail}")
        raise e
    except Exception as e:
        logging.error(f"시스템 오류: {str(e)}")
        raise HTTPException(status_code=500, detail="시스템 오류가 발생했습니다.")
