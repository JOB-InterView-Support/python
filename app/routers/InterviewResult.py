from fastapi import APIRouter, HTTPException, FastAPI
from app.utils.db_connection import get_oracle_connection
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from fastapi.responses import StreamingResponse
import os

# FastAPI 앱 생성
app = FastAPI()

# 로거 설정
logger = logging.getLogger("uvicorn.error")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인 허용
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

# 라우터 설정
router = APIRouter()

@router.get("/compare_self_introduce_interview/{uuid}")
async def compare_self_introduce_interview_with_uuid(uuid: str):
    """
    특정 UUID에 대한 자기소개서와 면접 비교 데이터 반환.
    """
    try:
        logger.info(f"[INFO] 요청받은 UUID: {uuid}")
        connection = get_oracle_connection()
        cursor = connection.cursor()

        query = """
            SELECT si.INTRO_NO, si.UUID, si.INTRO_TITLE, 
                   CASE 
                       WHEN i.CONPLETE_STATUS = 'Y' THEN 'Y'
                       WHEN i.CONPLETE_STATUS = 'N' THEN 'N'
                   END AS STATUS,
                   i.INT_ID
            FROM C##SS.SELF_INTRODUCE si
            INNER JOIN C##SS.INTERVIEW i 
            ON si.INTRO_NO = i.INTRO_NO
            WHERE si.INTRO_IS_DELETED = 'N' AND si.UUID = :uuid
        """
        logger.info(f"[INFO] 실행할 쿼리:\n{query}")

        # 쿼리 실행
        cursor.execute(query, {"uuid": uuid})
        result = [
            {
                "intro_no": row[0],
                "uuid": row[1],
                "intro_title": row[2],
                "status": row[3],  # Y 또는 N
                "int_id": row[4]   # 추가된 int_id
            }
            for row in cursor.fetchall()
        ]

        # 연결 종료
        cursor.close()
        connection.close()

        # 결과 확인
        if not result:
            logger.warning("[WARN] 해당 UUID에 대한 기록이 없습니다.")
            return {"message": "해당 UUID에 대한 기록이 없습니다."}

        logger.info(f"[INFO] 조회 결과: {result}")
        return result

    except Exception as e:
        logger.error(f"[ERROR] DB 처리 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"DB Error: {str(e)}")


@router.get("/interview_detail/{intro_no}/{int_no}")
async def get_interview_detail(intro_no: str, int_no: str):
    """
    특정 자기소개서 ID(intro_no)와 면접 ID(int_no)에 대한 영상 및 음성 파일 경로를 반환.
    """
    try:
        logger.info(f"[INFO] 요청받은 intro_no: {intro_no}, int_no: {int_no}")
        logger.info("[INFO] Oracle 데이터베이스 연결 시도")

        # Oracle 데이터베이스 연결
        connection = get_oracle_connection()
        cursor = connection.cursor()

        # 쿼리 작성
        query = """
            SELECT 
                iv.IV_PATH AS video_path, 
                ia.AUDIO_PATH AS audio_path
            FROM 
                C##SS.INTERVIEW_VIDEO iv
            INNER JOIN 
                C##SS.INTERVIEW_AUDIO ia 
                ON iv.INT_ID = ia.INT_ID
            INNER JOIN 
                C##SS.INTERVIEW i
                ON i.INT_ID = iv.INT_ID
            WHERE 
                i.INTRO_NO = :intro_no
                AND i.INT_ID = :int_no
        """

        logger.info(f"[INFO] 실행할 쿼리:\n{query}")
        logger.info("[INFO] 쿼리 실행 중...")

        # 쿼리 실행
        cursor.execute(query, {"intro_no": intro_no, "int_no": int_no})
        row = cursor.fetchone()

        logger.info(f"[INFO] 쿼리 결과: {row}")

        # 연결 종료
        cursor.close()
        connection.close()

        # 결과 확인
        if not row:
            logger.warning("[WARN] 해당 자기소개서 ID 또는 면접 ID에 대한 데이터가 없습니다.")
            raise HTTPException(
                status_code=404, detail="해당 자기소개서 ID 또는 면접 ID에 대한 데이터가 없습니다."
            )

        # 결과 반환
        return {
            "video_path": row[0],
            "audio_path": row[1]
        }

    except Exception as e:
        logger.error(f"[ERROR] DB 처리 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"DB Error: {str(e)}")


@app.get("/files/{file_path:path}")
async def serve_file(file_path: str):
    """
    정적 파일 제공: C:/JOBISIMG 디렉토리에서 파일 제공.
    """
    try:
        full_path = os.path.join("C:/JOBISIMG", file_path)
        logger.info(f"[INFO] 요청받은 파일 경로: {full_path}")

        def file_iterator():
            with open(full_path, "rb") as file:
                yield from file

        # StreamingResponse를 사용하여 파일 제공
        return StreamingResponse(file_iterator(), media_type="application/octet-stream")
    except Exception as e:
        logger.error(f"[ERROR] 파일 제공 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

# 라우터 추가
app.include_router(router)
