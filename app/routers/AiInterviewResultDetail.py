from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from ..utils.db_connection import get_oracle_connection
import os

router = APIRouter()

# 전역 변수 선언
global_iv_id = None


class InterviewIdRequest(BaseModel):
    interviewId: str


@router.post("/getResultVideo")
async def get_result_data(request: Request, data: InterviewIdRequest):
    interview_id = data.interviewId
    print(f"디테일 Received interviewId: {interview_id}")  # 콘솔에 interviewId 출력

    connection = get_oracle_connection()
    if not connection:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        cursor = connection.cursor()
        query = """
            SELECT IV_PATH
            FROM INTERVIEW_VIDEO
            WHERE INT_ID = :interview_id
        """
        cursor.execute(query, {"interview_id": interview_id})
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Video not found")

        # 절대 경로 제거, 파일 이름만 반환
        iv_path = result[0].replace("C:/JOBISIMG/VIDEO/", "")
        print(f"Video Path: {iv_path}")  # 확인을 위한 로그 출력
        return {"iv_path": iv_path}
    finally:
        connection.close()


class InterviewIdRequest(BaseModel):
    interviewId: str


@router.post("/getResultAudio")
async def get_result_audio(request: Request, data: InterviewIdRequest):
    interview_id = data.interviewId
    print(f"Received interviewId for audio: {interview_id}")

    connection = get_oracle_connection()
    if not connection:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        cursor = connection.cursor()
        query = """
            SELECT AUDIO_PATH
            FROM INTERVIEW_AUDIO
            WHERE INT_ID = :interview_id
        """
        cursor.execute(query, {"interview_id": interview_id})
        result = cursor.fetchone()
        print("DB 조회 결과 : ", result)

        if not result:
            raise HTTPException(status_code=404, detail="Audio not found")

        # 반환되는 경로 출력
        audio_path = result[0].replace("C:/JOBISIMG/AUDIO/", "")  # 절대 경로 제거
        print(f"Audio Path: {audio_path}")
        return {"audio_path": audio_path}
    finally:
        connection.close()


@router.post("/getIvId")
async def get_feelings(request: Request, data: InterviewIdRequest):
    global global_iv_id
    interview_id = data.interviewId
    print(f"감정 결과 가져오기 Received interviewId: {interview_id}")

    connection = get_oracle_connection()
    if not connection:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        cursor = connection.cursor()
        query = """
            SELECT IV_ID
            FROM INTERVIEW_VIDEO
            WHERE INT_ID = :interview_id
        """
        cursor.execute(query, {"interview_id": interview_id})
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="IV_ID not found")

        return {"iv_id": result[0]}  # result[0]가 IV_ID라고 가정합니다.

    finally:
        connection.close()


class IvIdRequest(BaseModel):
    iv_id: str


@router.post("/getFeelings")
async def get_feelings(data: IvIdRequest):
    iv_id = data.iv_id
    connection = get_oracle_connection()
    if not connection:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        cursor = connection.cursor()
        query = """
        SELECT IVF_ANGRY, IVF_DISGUST, IVF_FEAR, IVF_HAPPY, IVF_SAD, IVF_SURPRISED, IVF_NEUTRALITY
        FROM INTERVIEW_FEELINGS
        WHERE IV_ID = :iv_id
        """
        cursor.execute(query, {"iv_id": iv_id})
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Feelings data not found")

        feelings = {
            "angry": result[0],
            "disgust": result[1],
            "fear": result[2],
            "happy": result[3],
            "sad": result[4],
            "surprised": result[5],
            "neutrality": result[6]
        }

        return feelings
    finally:
        connection.close()


@router.post("/getGaze")
async def get_gaze(request: Request):
    print("시선 분석 결과 시작")
    # JSON 데이터 요청을 받음
    data = await request.json()
    iv_id = data.get("iv_id")

    print(f"Received iv_id: {iv_id}")

    connection = get_oracle_connection()
    if not connection:
        return {"message": "Database connection failed"}

    try:
        cursor = connection.cursor()
        # INTERVIEW_GAZE 테이블에서 데이터 가져오기
        query = """
            SELECT IVG_AVG, IVG_MIN, IVG_MAX
            FROM INTERVIEW_GAZE
            WHERE IV_ID = :iv_id
        """
        cursor.execute(query, {'iv_id': iv_id})
        result = cursor.fetchone()

        if not result:
            return {"message": "No gaze data found for the given iv_id"}

        # 결과를 반환
        gaze_data = {
            "IVG_AVG": result[0],
            "IVG_MIN": result[1],
            "IVG_MAX": result[2]
        }
        print("Gaze Data Retrieved:", gaze_data)
        return gaze_data
    except Exception as e:
        print("Error fetching gaze data:", str(e))
        raise HTTPException(status_code=500, detail="Error fetching gaze data")
    finally:
        connection.close()



@router.post("/getPosition")
async def get_position(request: Request):
    print("포지션 데이터 조회 시작")
    # JSON 데이터 요청을 받음
    data = await request.json()
    iv_id = data.get("iv_id")

    print(f"Received iv_id for Position: {iv_id}")

    connection = get_oracle_connection()
    if not connection:
        return {"message": "Database connection failed"}

    try:
        cursor = connection.cursor()
        # INTERVIEW_POSITION 테이블에서 데이터 가져오기
        query = """
            SELECT IVP_GOODPOSE, IVP_BEDNECK, IVP_BEDSHOULDER, IVP_BADPOSE
            FROM INTERVIEW_POSITION
            WHERE IV_ID = :iv_id
        """
        cursor.execute(query, {'iv_id': iv_id})
        result = cursor.fetchone()

        if not result:
            return {"message": "No position data found for the given iv_id"}

        # 결과를 반환
        position_data = {
            "IVP_GOODPOSE": result[0],
            "IVP_BEDNECK": result[1],
            "IVP_BEDSHOULDER": result[2],
            "IVP_BADPOSE": result[3],
        }
        print("Position Data Retrieved:", position_data)
        return position_data
    except Exception as e:
        print("Error fetching position data:", str(e))
        raise HTTPException(status_code=500, detail="Error fetching position data")
    finally:
        connection.close()



@router.post("/getSTT")
async def get_stt(request: Request):
    print("STT 데이터 조회 시작")
    # JSON 데이터 요청을 받음
    data = await request.json()
    interview_id = data.get("interviewId")

    # 받은 interviewId를 출력
    print(f"Received interviewId for STT: {interview_id}")

    # 데이터베이스 연결
    connection = get_oracle_connection()
    if not connection:
        return {"message": "Database connection failed"}

    try:
        cursor = connection.cursor()

        # INTERVIEW_AUDIO 테이블에서 AUDIO_ID 조회
        query_audio = """
            SELECT AUDIO_ID
            FROM INTERVIEW_AUDIO
            WHERE INT_ID = :interview_id
        """
        cursor.execute(query_audio, {'interview_id': interview_id})
        audio_result = cursor.fetchone()

        if not audio_result:
            print("No AUDIO_ID found for the given interviewId")
            return {"message": "No AUDIO_ID found for the given interviewId"}

        audio_id = audio_result[0]
        print(f"AUDIO_ID Retrieved: {audio_id}")

        # INTERVIEW_STT 테이블에서 STT_FILE_PATH 조회
        query_stt = """
            SELECT STT_FILE_PATH
            FROM INTERVIEW_STT
            WHERE AUDIO_ID = :audio_id
        """
        cursor.execute(query_stt, {'audio_id': audio_id})
        stt_result = cursor.fetchone()

        if not stt_result:
            print("No STT_FILE_PATH found for the given AUDIO_ID")
            return {"message": "No STT_FILE_PATH found for the given AUDIO_ID"}

        stt_file_path = stt_result[0]
        print(f"STT_FILE_PATH Retrieved: {stt_file_path}")

        # 텍스트 파일 읽기
        if not os.path.exists(stt_file_path):
            print(f"STT file not found at path: {stt_file_path}")
            return {"message": f"STT file not found at path: {stt_file_path}"}

        with open(stt_file_path, "r", encoding="utf-8") as file:
            stt_content = file.read()

        print(f"STT File Content:\n{stt_content}")

        # 최종 결과 반환
        return {"STT_FILE_CONTENT": stt_content}
    except Exception as e:
        print(f"Error processing STT file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing STT file")
    finally:
        connection.close()



