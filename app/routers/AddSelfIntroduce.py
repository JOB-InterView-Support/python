import logging
from fastapi import APIRouter, HTTPException
from app.utils.db_connection import get_oracle_connection
import openai
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel
import os
from fastapi.responses import JSONResponse

# .env 파일 로드
load_dotenv()

# 라우터 생성
router = APIRouter()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# OpenAI API 키 설정
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logger.error("OpenAI API Key가 로드되지 않았습니다.")
    raise HTTPException(status_code=500, detail="OpenAI API Key가 설정되지 않았습니다.")

# 전역 상태 변수 정의
add_self_intro_status = "idle"  # 초기 상태는 idle

# 요청 데이터를 위한 Pydantic 모델 정의
class InsertSelfIntroduceRequest(BaseModel):
    intro_no: str  # 자기소개서 번호

# OpenAI를 이용한 자기소개서 첨삭 및 피드백 생성
def process_self_introduction(content, model="gpt-3.5-turbo"):
    logger.info("OpenAI API 호출 시작")

    try:
        trimmed_content = content[:1200]
        logger.info(f"자기소개서 내용 1200자로 제한: {trimmed_content}")

        prompt = f"""
        다음은 제가 작성한 자기소개서의 일부입니다. (총 1200자 제한)
        이 자기소개서를 바탕으로 문맥과 내용을 개선하고 피드백을 작성해주세요. 

        **첨삭된 자기소개서**:
        내용

        **피드백**:
        내용

        자기소개서 내용:
        {trimmed_content}
        """
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": "당신은 문서 첨삭 및 피드백 전문가입니다."},
                {"role": "user", "content": prompt}
            ]
        )
        logger.info("OpenAI API 호출 성공")
        return response.choices[0].message["content"]

    except openai.error.OpenAIError as e:
        logger.error(f"OpenAI API 호출 실패: {e}")
        return None

@router.put("/insert_self_introduce")
async def insert_self_introduction(request: InsertSelfIntroduceRequest):
    global add_self_intro_status
    add_self_intro_status = "processing"  # 작업 시작
    intro_no = request.intro_no
    logger.info(f"API 요청 수신: intro_no={intro_no}")

    connection = get_oracle_connection()
    if not connection:
        logger.error("데이터베이스 연결 실패")
        add_self_intro_status = "idle"
        raise HTTPException(status_code=500, detail="데이터베이스 연결 실패")

    try:
        cursor = connection.cursor()
        logger.info("커서 생성 완료")

        # DB에서 기존 데이터 조회
        logger.info(f"SELF_INTRODUCE 테이블에서 intro_no={intro_no} 데이터 조회 중")
        cursor.execute(
            """
            SELECT INTRO_CONTENTS, INTRO_TITLE, APPLICATION_COMPANY_NAME, WORK_TYPE, CERTIFICATE
            FROM C##SS.SELF_INTRODUCE
            WHERE INTRO_NO = :intro_no
            """,
            {"intro_no": intro_no}
        )

        result = cursor.fetchone()
        if not result:
            logger.warning(f"intro_no={intro_no}에 해당하는 데이터가 없습니다.")
            add_self_intro_status = "idle"
            raise HTTPException(status_code=404, detail="자기소개서를 찾을 수 없습니다.")

        intro_contents, intro_title, company_name, work_type, certificate = result

        # OpenAI API 호출
        processed_content = process_self_introduction(intro_contents)
        if not processed_content:
            add_self_intro_status = "idle"
            raise HTTPException(status_code=500, detail="OpenAI API 호출 실패")

        # 응답 데이터 처리
        split_index = processed_content.find("피드백:")
        if split_index == -1:
            add_self_intro_status = "idle"
            raise HTTPException(status_code=500, detail="OpenAI 응답에서 피드백을 분리할 수 없습니다.")

        updated_content = processed_content[:split_index].strip()
        feedback = processed_content[split_index + 4:].strip()
        logger.info("첨삭 및 피드백 분리 완료")

        if "(첨삭)" not in intro_title:
            intro_title += " (첨삭)"

        # 기존 intro_no와 동일한 prefix 확인
        base_intro_no = intro_no.split("_")[0]
        logger.info(f"기존 intro_no의 prefix: {base_intro_no}")

        # 동일 prefix의 최대 번호 찾기
        cursor.execute(
            """
            SELECT MAX(INTRO_NO)
            FROM C##SS.SELF_INTRODUCE
            WHERE INTRO_NO LIKE :base_intro_no || '_%'
            """,
            {"base_intro_no": base_intro_no}
        )
        max_intro_no = cursor.fetchone()[0]
        logger.info(f"동일 prefix의 최대 intro_no: {max_intro_no}")

        # 새로운 intro_no 생성
        if max_intro_no:
            current_suffix = int(max_intro_no.split("_")[-1])
            new_intro_no = f"{base_intro_no}_{current_suffix + 1}"
        else:
            new_intro_no = f"{base_intro_no}_1"
        logger.info(f"새로운 intro_no 생성: {new_intro_no}")

        # DB에 새 레코드 삽입
        cursor.execute(
            """
            INSERT INTO C##SS.SELF_INTRODUCE
            (INTRO_NO, INTRO_TITLE, INTRO_CONTENTS, INTRO_IS_EDITED, INTRO_FEEDBACK, INTRO_DATE, APPLICATION_COMPANY_NAME, WORK_TYPE, CERTIFICATE)
            VALUES (:new_intro_no, :intro_title, :updated_content, :intro_is_edited, :feedback, :update_date, :company_name, :work_type, :certificate)
            """,
            {
                "new_intro_no": new_intro_no,
                "intro_title": intro_title,
                "updated_content": updated_content,
                "intro_is_edited": 'Y',
                "feedback": feedback,
                "update_date": datetime.now(),
                "company_name": company_name,
                "work_type": work_type,
                "certificate": certificate
            }
        )
        connection.commit()
        logger.info(f"새로운 데이터 생성 성공: new_intro_no={new_intro_no}")
        add_self_intro_status = "complete"
        return {"status": "success", "message": "작업이 완료되었습니다.", "new_intro_no": new_intro_no}

    except Exception as e:
        connection.rollback()
        add_self_intro_status = "idle"
        logger.error(f"데이터베이스 등록 실패: {e}")
        raise HTTPException(status_code=500, detail=f"데이터베이스 등록 실패: {e}")

    finally:
        connection.close()
        logger.info("데이터베이스 연결 해제")

@router.get("/addSelfIntroduce/status")
async def get_status():
    global add_self_intro_status
    logger.info(f"현재 상태: {add_self_intro_status}")
    return {"status": add_self_intro_status}

@router.get("/addSelfIntroduce/self-introduce/{intro_no}")
async def get_self_introduce(intro_no: str):
    logger.info(f"요청받은 intro_no: {intro_no}")
    connection = get_oracle_connection()
    if not connection:
        raise HTTPException(status_code=500, detail="데이터베이스 연결 실패")

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT INTRO_TITLE, INTRO_CONTENTS, APPLICATION_COMPANY_NAME, WORK_TYPE, CERTIFICATE, INTRO_FEEDBACK
            FROM C##SS.SELF_INTRODUCE
            WHERE INTRO_NO = :intro_no
            """,
            {"intro_no": intro_no}
        )
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="자기소개서를 찾을 수 없습니다.")

        return JSONResponse(content={
            "introTitle": result[0],
            "introContents": result[1],
            "applicationCompanyName": result[2],
            "workType": result[3],
            "certificate": result[4],
            "introFeedback": result[5],
        })
    finally:
        connection.close()

@router.get("/addSelfIntroduce/test_db")
async def test_db():
    connection = get_oracle_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM C##SS.SELF_INTRODUCE")
        count = cursor.fetchone()
        return {"total_rows": count[0]}
    except Exception as e:
        logger.error(f"DB 테스트 중 오류 발생: {e}")
        return {"error": str(e)}
    finally:
        connection.close()
