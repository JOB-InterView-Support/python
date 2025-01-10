import os
import logging
import datetime
import requests
from dotenv import load_dotenv
from fastapi import APIRouter, Form, HTTPException, FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text

# .env 파일 로드
load_dotenv()

# 환경 변수 가져오기
NCLOUD_ACCESS_KEY = os.getenv("NCLOUD_ACCESS_KEY")
NCLOUD_SECRET_KEY = os.getenv("NCLOUD_SECRET_KEY")
NCLOUD_BUCKET_NAME = os.getenv("NCLOUD_BUCKET_NAME")
CLOVA_CLIENT_ID = os.getenv("CLOVA_CLIENT_ID")
CLOVA_CLIENT_SECRET = os.getenv("CLOVA_CLIENT_SECRET")
DATABASE_URL = os.getenv("DATABASE_URL")
LOCAL_AUDIO_FOLDER = os.getenv("LOCAL_AUDIO_FOLDER")
LOCAL_TEXT_FOLDER = os.getenv("LOCAL_TEXT_FOLDER")

# FastAPI 설정
app = FastAPI(docs_url="/docs", redoc_url="/redoc")
router = APIRouter()

# 데이터베이스 엔진 설정
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine)

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)

# 데이터 모델 정의
class VoiceTranscriptionResponse(BaseModel):
    transcription: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# DB에서 음성 파일 경로 조회
def get_audio_path_from_db(audio_id: str, int_id: str) -> str:
    logging.info(f"DB 조회 시작: audio_id={audio_id}, int_id={int_id}")

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
                logging.info(f"DB 조회 성공: {audio_path}")
                return audio_path
            else:
                raise HTTPException(status_code=404, detail="해당 음성 파일을 찾을 수 없습니다.")
        except Exception as e:
            logging.error(f"DB 조회 중 오류: {str(e)}")
            raise HTTPException(status_code=500, detail="DB 조회 중 오류가 발생했습니다.")

# 네이버 Object Storage에 파일 업로드
def upload_to_object_storage(bucket_name: str, file_path: str, object_name: str) -> str:
    logging.info(f"Object Storage 업로드 시작: bucket={bucket_name}, file_path={file_path}, object_name={object_name}")
    try:
        endpoint = f"https://kr.object.ncloudstorage.com/{bucket_name}/{object_name}"
        logging.debug(f"Object Storage 엔드포인트: {endpoint}")
        with open(file_path, "rb") as f:
            headers = {
                "Content-Type": "application/octet-stream",
                "x-ncp-apigw-timestamp": str(int(datetime.datetime.utcnow().timestamp() * 1000)),
                "x-ncp-iam-access-key": NCLOUD_ACCESS_KEY,
                "x-ncp-apigw-api-key": NCLOUD_SECRET_KEY,
            }
            logging.debug(f"헤더: {headers}")
            response = requests.put(endpoint, headers=headers, data=f)
            logging.debug(f"응답 상태 코드: {response.status_code}")
            logging.debug(f"응답 본문: {response.text}")
            if response.status_code != 200:
                raise Exception(f"Object Storage 업로드 실패: {response.text}")
        logging.info(f"Object Storage 업로드 성공: {endpoint}")
        return endpoint
    except Exception as e:
        logging.error(f"Object Storage 업로드 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Object Storage 업로드 중 오류 발생: {str(e)}")

# CLOVA Speech Long STT API 호출
def call_clova_speech_api(uri: str) -> str:
    logging.info(f"CLOVA Speech Long STT API 호출 시작: uri={uri}")
    try:
        url = "https://naveropenapi.apigw.ntruss.com/stt/v1/recognize"
        headers = {
            "X-NCP-APIGW-API-KEY-ID": CLOVA_CLIENT_ID,
            "X-NCP-APIGW-API-KEY": CLOVA_CLIENT_SECRET,
            "Content-Type": "application/json",
        }
        data = {"url": uri}
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            logging.error(f"API 호출 실패: {response.text}")
            raise Exception(f"API 호출 실패: {response.text}")
        logging.info("CLOVA Speech Long STT API 호출 성공")
        return response.json().get("text", "")
    except Exception as e:
        logging.error(f"CLOVA Speech API 호출 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"CLOVA Speech API 호출 중 오류 발생: {str(e)}")

# 음성을 텍스트로 변환하는 엔드포인트
@router.post("/Clova", response_model=VoiceTranscriptionResponse)
async def stt_processing(
    audio_id: str = Form(...),
    int_id: str = Form(...),
):
    try:
        logging.info(f"STT 처리 시작: audio_id={audio_id}, int_id={int_id}")

        # 1. DB에서 음성 파일 경로 조회
        audio_path = get_audio_path_from_db(audio_id, int_id)
        if not os.path.exists(audio_path):
            logging.error(f"파일이 존재하지 않음: {audio_path}")
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

        # 2. 원본 음성 파일 업로드 (Bucket: AUDIO)
        original_object_name = f"AUDIO/{os.path.basename(audio_path)}"
        original_uri = upload_to_object_storage(NCLOUD_BUCKET_NAME, audio_path, original_object_name)

        # 3. CLOVA Speech Long STT API 호출
        transcription = call_clova_speech_api(original_uri)

        # 4. 텍스트 파일로 저장
        text_file_name = f"{audio_id}_transcription.txt"
        text_file_path = os.path.join(LOCAL_TEXT_FOLDER, text_file_name)
        with open(text_file_path, "w", encoding="utf-8") as file:
            file.write(transcription)

        logging.info("STT 처리 완료")
        return {"transcription": transcription}

    except HTTPException as e:
        logging.error(f"API 요청 처리 중 오류: {str(e)}")
        raise e
    except Exception as e:
        logging.error(f"시스템 오류: {str(e)}")
        raise HTTPException(status_code=500, detail="시스템 오류가 발생했습니다.")
