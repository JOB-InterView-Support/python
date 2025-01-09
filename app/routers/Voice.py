import os
from fastapi import APIRouter, Form, HTTPException, FastAPI
from pydantic import BaseModel
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
from pydub import AudioSegment
from google.cloud import storage


# FastAPI 인스턴스 생성
app = FastAPI(docs_url="/docs", redoc_url="/redoc")
router = APIRouter()

# 데이터베이스 URL 및 엔진 설정
DATABASE_URL = "oracle+cx_oracle://C##SS:1234@ktj0514.synology.me:1521/xe"
engine = create_engine(DATABASE_URL, echo=True)

# 세션 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)

# 데이터 모델 정의
class VoiceTranscriptionRequest(BaseModel):
    language_code: str = "ko-KR"  # 기본 언어는 한국어

class VoiceTranscriptionResponse(BaseModel):
    transcription: str  # 변환된 텍스트

# DB에서 음성 파일 경로 조회
def get_audio_path_from_db(audio_id: str, int_id: str) -> str:
    with SessionLocal() as session:
        try:
            query = text("""
                SELECT AUDIO_PATH
                FROM INTERVIEW_AUDIO
                WHERE AUDIO_ID = :audio_id AND INT_ID = :int_id
            """)
            result = session.execute(query, {"audio_id": audio_id, "int_id": int_id}).fetchone()
            if result:
                audio_path = result[0]
                if not audio_path:
                    raise HTTPException(status_code=404, detail="DB에서 조회된 경로가 비어 있습니다.")
                if not os.path.exists(audio_path):
                    raise HTTPException(status_code=404, detail=f"파일 경로가 유효하지 않습니다: {audio_path}")
                return audio_path
            else:
                raise HTTPException(status_code=404, detail="해당 음성 파일을 찾을 수 없습니다.")
        except Exception as e:
            logging.error(f"DB 조회 중 오류: {str(e)}")
            raise HTTPException(status_code=500, detail="DB 조회 중 오류가 발생했습니다.")
        finally:
            session.close()  # 세션을 항상 닫아줌

# 스테레오 파일을 모노로 변환
def convert_to_mono(file_path: str) -> str:
    mono_file_path = file_path.replace(".mp3", "_mono.mp3")
    try:
        audio = AudioSegment.from_file(file_path)
        if audio.channels > 1:
            audio = audio.set_channels(1)
            audio.export(mono_file_path, format="mp3")
            logging.info(f"오디오 파일이 모노로 변환되었습니다: {mono_file_path}")
            return mono_file_path
        return file_path
    except Exception as e:
        logging.error(f"오디오 파일 모노 변환 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail="오디오 파일 모노 변환 중 오류 발생")

def preprocess_and_merge_audio(file_path: str, output_folder: str) -> str:
    """
    음성 파일을 처리하고 하나의 파일로 저장합니다.
    :param file_path: 입력 파일 경로
    :param output_folder: 처리된 파일이 저장될 폴더
    :return: 처리된 파일 경로
    """
    try:
        # 파일 불러오기
        audio = AudioSegment.from_file(file_path)

        # 앞부분 5초 제거
        start_trim = 5 * 1000  # 5초 (밀리초 단위)
        audio = audio[start_trim:]

        # 8분 초과 부분 제거
        max_duration = 8 * 60 * 1000  # 8분 (밀리초 단위)
        if len(audio) > max_duration:
            audio = audio[:max_duration]

        # 변환된 파일 저장
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        processed_file_path = os.path.join(output_folder, "processed_audio.wav")
        audio.export(processed_file_path, format="wav", parameters=["-ar", "16000", "-ac", "1"])
        logging.info(f"처리된 파일 저장 완료: {processed_file_path}")

        return processed_file_path

    except Exception as e:
        logging.error(f"음성 파일 처리 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail="음성 파일 처리 중 오류 발생")

def upload_to_gcs(bucket_name: str, source_file_path: str, destination_blob_name: str) -> str:
    """
    Google Cloud Storage에 파일을 업로드합니다.
    :param bucket_name: GCS 버킷 이름
    :param source_file_path: 업로드할 로컬 파일 경로
    :param destination_blob_name: GCS에 저장될 파일 경로
    :return: 업로드된 파일의 GCS URI
    """
    try:
        # GCS 클라이언트 생성
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)

        # 파일 업로드
        blob.upload_from_filename(source_file_path)

        # GCS URI 반환
        gcs_uri = f"gs://{bucket_name}/{destination_blob_name}"
        logging.info(f"GCS에 파일 업로드 완료: {gcs_uri}")
        return gcs_uri
    except Exception as e:
        logging.error(f"GCS 업로드 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"GCS 업로드 중 오류 발생: {str(e)}")

from google.cloud import speech

async def transcribe_audio_from_gcs(gcs_uri: str, language_code: str = "ko-KR") -> str:
    """
    Google Cloud Speech-to-Text API를 사용하여 GCS의 음성 파일을 텍스트로 변환합니다.
    :param gcs_uri: Google Cloud Storage의 파일 URI
    :param language_code: 음성 인식 언어 코드
    :return: 변환된 텍스트
    """
    try:
        client = speech.SpeechClient()

        # 오디오 및 설정
        audio = speech.RecognitionAudio(uri=gcs_uri)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code,
        )

        # 비동기 요청
        logging.info(f"GCS 파일에서 STT 작업 시작: {gcs_uri}")
        operation = client.long_running_recognize(config=config, audio=audio)

        # 작업 완료 대기
        response = operation.result(timeout=300)

        # 결과 병합
        transcription = " ".join(result.alternatives[0].transcript for result in response.results)
        logging.info(f"텍스트 변환 완료: {transcription}")
        return transcription.strip()

    except Exception as e:
        logging.error(f"Google STT 호출 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Google STT 호출 중 오류 발생: {str(e)}")

async def transcribe_audio_files(audio_files: list, language_code: str = "ko-KR") -> list:
    """
    분할된 음성 파일들을 Google STT로 텍스트로 변환하고, 변환 완료 후 파일 삭제합니다.
    :param audio_files: 음성 파일 경로 리스트
    :param language_code: 음성 인식 언어 코드
    :return: 변환된 텍스트 리스트
    """
    transcriptions = []

    for file_path in audio_files:
        try:
            # GCS에 업로드
            bucket_name = "project_jobis"
            destination_blob_name = f"audio/{os.path.basename(file_path)}"
            gcs_uri = upload_to_gcs(bucket_name, file_path, destination_blob_name)

            # Google STT 호출
            transcription = await transcribe_audio_from_gcs(gcs_uri, language_code)
            transcriptions.append(transcription)
            logging.info(f"{file_path} -> 변환된 텍스트: {transcription}")

        except Exception as e:
            logging.error(f"음성 파일 변환 중 오류 발생: {str(e)}")
            transcriptions.append("오류 발생")

        finally:
            # 변환 완료 후 파일 삭제
            try:
                os.remove(file_path)
                logging.info(f"파일 삭제 완료: {file_path}")
            except Exception as delete_error:
                logging.error(f"파일 삭제 중 오류 발생: {delete_error}")

    return transcriptions


def upload_to_gcs_and_local(bucket_name: str, local_file_path: str, gcs_folder: str, local_folder: str) -> str:
    """
    파일을 GCS와 로컬에 업로드 및 저장합니다.
    :param bucket_name: GCS 버킷 이름
    :param local_file_path: 로컬 파일 경로
    :param gcs_folder: GCS에 저장될 폴더 이름
    :param local_folder: 로컬에 저장될 폴더 경로
    :return: GCS URI
    """
    try:
        # GCS에 업로드
        gcs_filename = os.path.join(gcs_folder, os.path.basename(local_file_path)).replace("\\", "/")
        gcs_uri = upload_to_gcs(bucket_name, local_file_path, gcs_filename)

        # 로컬 폴더에 복사
        if not os.path.exists(local_folder):
            os.makedirs(local_folder)

        local_destination = os.path.join(local_folder, os.path.basename(local_file_path))
        os.replace(local_file_path, local_destination)
        logging.info(f"파일이 로컬에 저장되었습니다: {local_destination}")

        return gcs_uri
    except Exception as e:
        logging.error(f"GCS 및 로컬 저장 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"GCS 및 로컬 저장 중 오류 발생: {str(e)}")
def save_transcriptions_to_file(transcriptions: list, output_folder: str, base_filename: str) -> str:
    """
    변환된 텍스트를 하나의 파일로 저장합니다.
    :param transcriptions: 변환된 텍스트 리스트
    :param output_folder: 텍스트 파일이 저장될 폴더
    :param base_filename: 텍스트 파일 이름의 기본값
    :return: 저장된 텍스트 파일 경로
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    text_file_path = os.path.join(output_folder, f"{base_filename}.txt")
    try:
        with open(text_file_path, "w", encoding="utf-8") as file:
            for i, transcription in enumerate(transcriptions, start=1):
                file.write(f"Segment {i}:\n")
                file.write(transcription + "\n\n")
        logging.info(f"텍스트 파일 저장 완료: {text_file_path}")
        return text_file_path
    except Exception as e:
        logging.error(f"텍스트 파일 저장 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail="텍스트 파일 저장 중 오류가 발생했습니다.")

@router.post("/Voice", response_model=dict)
async def stt_processing(
    audio_id: str = Form(...),
    int_id: str = Form(...),
    language_code: str = Form("ko-KR"),
    local_audio_folder: str = Form("C:\\JOBISIMG\\AUDIO"),
    local_audio_division_folder: str = Form("C:\\JOBISIMG\\AUDIO_DIVISION"),
    local_text_folder: str = Form("C:\\JOBISIMG\\TEXT"),
    bucket_name: str = Form("project_jobis")
):
    """
    음성 파일을 처리하고 변환 결과를 GCS 및 로컬에 저장합니다.
    :param audio_id: DB에서 조회할 AUDIO_ID
    :param int_id: DB에서 조회할 INT_ID
    :param language_code: Google STT 변환에 사용할 언어 코드
    :param local_audio_folder: 로컬에 저장될 오디오 음성 파일 폴더
    :param local_audio_division_folder: 로컬에 저장될 변환된 파일 폴더
    :param local_text_folder: 로컬에 저장될 텍스트 파일 폴더
    :param bucket_name: GCS 버킷 이름
    :return: 변환된 텍스트 파일 경로 및 텍스트 리스트
    """
    try:
        # 1. DB에서 음성 파일 경로 조회
        audio_path = get_audio_path_from_db(audio_id, int_id)
        if not os.path.exists(audio_path):
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

        # 2. 원본 오디오 파일 GCS 및 로컬에 저장
        upload_to_gcs_and_local(bucket_name, audio_path, "AUDIO", local_audio_folder)

        # 3. 음성 파일 처리 및 하나의 파일로 저장
        processed_audio_path = preprocess_and_merge_audio(audio_path, local_audio_division_folder)

        # 4. 처리된 파일을 GCS에 업로드 및 텍스트로 변환
        gcs_uri = upload_to_gcs_and_local(bucket_name, processed_audio_path, "AUDIO_DIVISION", local_audio_division_folder)
        transcription = await transcribe_audio_from_gcs(gcs_uri, language_code)

        # 5. 변환된 텍스트를 하나의 파일로 저장
        text_file_path = save_transcriptions_to_file([transcription], local_text_folder, f"{audio_id}_transcription")

        # 6. 텍스트 파일을 GCS에 업로드
        upload_to_gcs_and_local(bucket_name, text_file_path, "TEXT", local_text_folder)

        # 결과 반환
        return {"text_file_path": text_file_path, "transcription": transcription}

    except HTTPException as e:
        logging.error(f"API 요청 처리 중 오류: {str(e.detail)}")
        raise e
    except Exception as e:
        logging.error(f"시스템 오류: {str(e)}")
        raise HTTPException(status_code=500, detail="시스템 오류가 발생했습니다.")
