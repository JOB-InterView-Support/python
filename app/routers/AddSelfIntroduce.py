import logging
from fastapi import APIRouter, HTTPException
from app.utils.db_connection import get_oracle_connection
import openai
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel
import os

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

# Pydantic 모델 정의
class InsertSelfIntroduceRequest(BaseModel):
    intro_no: str  # 자기소개서 번호
    uuid: str  # 사용자 UUID

# OpenAI API 호출 함수
def process_self_introduction(content, model="gpt-3.5-turbo"):
    """
    OpenAI API를 호출하여 자기소개서 첨삭 및 피드백 생성.
    """
    logger.info("OpenAI API 호출 시작")
    try:
        # OpenAI 입력 제한에 맞게 자기소개서 내용을 1200자로 제한
        trimmed_content = content[:1200]  # OpenAI 입력 제한 적용
        logger.info(f"자기소개서 내용 1200자로 제한: {trimmed_content}")

        # OpenAI 프롬프트 작성
        prompt = f"""
        다음은 제가 작성한 자기소개서의 일부입니다. (총 1200자 제한)
        이 자기소개서를 바탕으로 문맥과 내용을 개선하고 피드백을 작성해.
        그리고 피드백은 자기소개서의 부족한부분을 ~부족하다 ,~필요하다 이런식으로 피드백 작성해

        반드시 아래 형식을 따라:

        **첨삭된 자기소개서**:
        (첨삭된 내용)

        **피드백**:
        (피드백 내용)

        자기소개서 내용:
        {trimmed_content}
        """

        # OpenAI API 호출
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": "당신은 면접담당이며  문서 첨삭 및 피드백 전문가입니다."},
                {"role": "user", "content": prompt}
            ]
        )
        logger.info("OpenAI API 호출 성공")
        return response.choices[0].message["content"]

    except openai.error.OpenAIError as e:
        logger.error(f"OpenAI API 호출 실패: {e}")
        raise HTTPException(status_code=500, detail=f"OpenAI API 호출 실패: {e}")

@router.post("/insert_self_introduce")
async def insert_self_introduction(request: InsertSelfIntroduceRequest):
    """
    자기소개서 첨삭 요청 API 엔드포인트.
    """
    global add_self_intro_status
    add_self_intro_status = "processing"  # 상태를 '처리 중'으로 변경
    intro_no = request.intro_no  # 요청에서 전달된 자기소개서 번호
    user_uuid = request.uuid  # 요청에서 전달된 사용자 UUID
    logger.info(f"API 요청 수신: intro_no={intro_no}, uuid={user_uuid}")

    # 데이터베이스 연결 생성
    connection = get_oracle_connection()
    if not connection:
        logger.error("데이터베이스 연결 실패")
        add_self_intro_status = "idle"
        raise HTTPException(status_code=500, detail="데이터베이스 연결 실패")

    try:
        cursor = connection.cursor()
        logger.info("커서 생성 완료")

        # 기존 자기소개서 조회
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

        # 조회 결과에서 데이터 분리
        intro_contents, intro_title, company_name, work_type, certificate = result

        # OpenAI API 호출
        processed_content = process_self_introduction(intro_contents)

        # 응답 데이터 처리
        try:
            updated_content = processed_content.split("**첨삭된 자기소개서**:")[1].split("**피드백**:")[0].strip()
            feedback = processed_content.split("**피드백**:")[1].strip()
        except (IndexError, ValueError) as e:
            logger.error(f"OpenAI 응답에서 예상된 형식을 찾을 수 없습니다: {e}")
            add_self_intro_status = "idle"
            raise HTTPException(status_code=500, detail="OpenAI 응답에서 형식을 찾을 수 없습니다.")

        # 제목에 "(첨삭)" 추가
        if "(첨삭)" not in intro_title:
            intro_title += " (첨삭)"

        # 새로운 intro_no 생성
        current_time = datetime.now().strftime("%Y%m%d%H%M%S")  # 현재 시간 추가
        new_intro_no = f"{intro_no}_{current_time}"
        if len(new_intro_no) > 255:  # 255바이트 제한 처리
            max_length = 255 - len(current_time) - 1
            new_intro_no = f"{intro_no[:max_length]}_{current_time}"

        logger.info(f"새로운 intro_no 생성: {new_intro_no}")

        # DB 삽입 (UUID 포함)
        db_data = {
            "new_intro_no": new_intro_no,
            "intro_title": intro_title,
            "updated_content": updated_content,
            "intro_is_edited": 'Y',
            "feedback": feedback,
            "update_date": datetime.now(),
            "company_name": company_name,
            "work_type": work_type,
            "certificate": certificate,
            "user_uuid": user_uuid,
        }

        # 로깅: DB에 삽입될 데이터
        logger.info("데이터베이스에 저장될 값:")
        for key, value in db_data.items():
            logger.info(f"{key}: {value}")

        # 데이터베이스에 삽입
        cursor.execute(
            """
            INSERT INTO C##SS.SELF_INTRODUCE
            (INTRO_NO, INTRO_TITLE, INTRO_CONTENTS, INTRO_IS_EDITED, INTRO_FEEDBACK, INTRO_DATE, APPLICATION_COMPANY_NAME, WORK_TYPE, CERTIFICATE, UUID)
            VALUES (:new_intro_no, :intro_title, :updated_content, :intro_is_edited, :feedback, :update_date, :company_name, :work_type, :certificate, :user_uuid)
            """,
            db_data
        )

        # 커밋하여 변경 사항 저장
        connection.commit()
        logger.info(f"새로운 데이터 생성 성공: new_intro_no={new_intro_no}")
        add_self_intro_status = "complete"  # 상태를 '완료'로 설정
        return {"status": "success", "message": "작업이 완료되었습니다.", "new_intro_no": new_intro_no}

    except Exception as e:
        # 예외 발생 시 트랜잭션 롤백
        connection.rollback()
        logger.error(f"데이터베이스 등록 실패: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 등록 실패")
    finally:
        # 커넥션 종료
        connection.close()
        logger.info("데이터베이스 연결 해제")
