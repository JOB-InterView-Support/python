import logging
import os
from http.client import HTTPException

import requests
import json

from dotenv import load_dotenv
from fastapi import APIRouter


# .env 파일에서 환경 변수를 불러오기 위해 dotenv 라이브러리를 사용함
load_dotenv()

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



# 환경 변수에서 Clova Speech API 키와 호출 URL을 가져옴
Clova_Secret_Key = os.getenv('Clova_Secret_Key')  # Clova Speech API 비밀번호 같은 것
Clova_invoke_url = os.getenv('invoke_url')  # Clova Speech API가 동작하는 주소

class ClovaSpeechClient:
    # Clova Speech API를 호출하기 위한 URL 설정
    invoke_url = Clova_invoke_url  # 가져온 URL 저장
    secret = Clova_Secret_Key  # 가져온 비밀번호 저장


    def req_upload(self, file, completion, callback=None, userdata=None, \
    	forbiddens=None, boostings=None, wordAlignment=True, \
        	fullText=True, diarization=None, sed=None):
        request_body = {
            'language': 'ko-KR',
            'completion': completion,
            'callback': callback,
            'userdata': userdata,
            'wordAlignment': wordAlignment,
            'fullText': fullText,
            'forbiddens': forbiddens,
            'boostings': boostings,
            'diarization': diarization,
            'sed': sed,
        }
        headers = {
            'Accept': 'application/json;UTF-8',
            'X-CLOVASPEECH-API-KEY': self.secret
        }
        print(json.dumps(request_body, ensure_ascii=False).encode('UTF-8'))
        files = {
            'media': open(file, 'rb'),
            'params': (None, json.dumps(request_body, \
            			ensure_ascii=False).encode('UTF-8'), \
                        		'application/json')
        }
        response = requests.post(headers=headers, url=self.invoke_url \
        			+ '/recognizer/upload', files=files)
        return response


if __name__ == '__main__':
    res = ClovaSpeechClient().req_upload(file='C:/JOBISIMG/AUDIO/1f105374-1b87-44d9-b647-c63834a18fa7_INTRO_1f105374-1b87-44d9-b647-c63834a18fa71736312933816_20250108192051_1_1.mp3', completion='sync')
    result = res.json()

    # 화자별 인식 결과 segment 추출
    segments = result.get('segments', [])
    speaker_segments = []
    for segment in segments:
        speaker_label = segment['speaker']['label']
        text = segment['text']
        speaker_segments.append({'speaker': speaker_label, 'text': text})

    # 화자별 인식 결과 segment 출력
    for speaker_segment in speaker_segments:
        speaker_label = speaker_segment['speaker']
        text = speaker_segment['text']
        print(f'Speaker {speaker_label}: {text}')