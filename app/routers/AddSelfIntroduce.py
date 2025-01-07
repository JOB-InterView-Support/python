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
openai_api_key = os.getenv("openai_api_key")
if not openai_api_key:
    logger.error("OpenAI API Key가 로드되지 않았습니다.")
    raise HTTPException(status_code=500, detail="OpenAI API Key가 설정되지 않았습니다.")

# 전역 상태 변수 정의
add_self_intro_status = False  # 초기 상태는 False

# 요청 데이터를 위한 Pydantic 모델 정의
class UpdateSelfIntroduceRequest(BaseModel):
    intro_no: str  # 자기소개서 번호


# OpenAI를 이용한 자기소개서 첨삭 및 피드백 생성
def process_self_introduction(content, model="gpt-3.5-turbo"):
    """
    OpenAI API를 호출하여 자기소개서를 첨삭하고 피드백을 생성합니다.
    - 입력: 자기소개서 내용 (최대 1200자)
    - 출력: 첨삭된 자기소개서 내용과 피드백
    """
    logger.info("OpenAI API 호출 시작")
    try:
        # 자기소개서 내용을 1200자로 제한
        trimmed_content = content[:1200]
        logger.info(f"자기소개서 내용 1200자로 제한: 길이={len(trimmed_content)}")

        # OpenAI에 전달할 프롬프트 생성
        logger.info("OpenAI에 전달할 프롬프트 생성 중")
        prompt = f"""
        다음은 제가 작성한 자기소개서의 일부입니다. (총 1200자 제한)
        이 자기소개서를 바탕으로 문맥과 내용을 개선하고 피드백을 작성해주세요. 

        **첨삭된 자기소개서**와 **피드백**을 각각 아래 형식에 맞춰 작성해주세요:

        **첨삭된 자기소개서**:
        내용

        **피드백**:
        내용

        자기소개서 내용:
        {trimmed_content}
        """
        logger.debug(f"OpenAI 프롬프트: {prompt}")

        # OpenAI API 호출
        response = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "system", "content": "당신은 문서 첨삭 및 피드백 전문가입니다."},
                      {"role": "user", "content": prompt}]
        )
        logger.info("OpenAI API 호출 성공")
        content = response.choices[0].message["content"]
        logger.debug(f"OpenAI API 응답: {content}")
        return content
    except openai.error.OpenAIError as e:
        logger.error(f"OpenAI API 호출 중 오류 발생: {e}")
        return None


@router.put("/update_self_introduce")
async def update_self_introduction(request: UpdateSelfIntroduceRequest):
    """
    자기소개서를 첨삭하고 업데이트하는 API.
    1. DB에서 자기소개서를 조회합니다.
    2. OpenAI를 호출하여 첨삭된 내용과 피드백을 생성합니다.
    3. DB에 업데이트하고, intro_no에 `_번호`를 추가하여 고유한 번호를 생성합니다.
    """
    global add_self_intro_status  # 전역 상태 변수 사용
    add_self_intro_status = "processing"  # 요청 처리 시작 시 상태를 "processing"으로 변경
    intro_no = request.intro_no.lower()  # intro_no는 소문자로 변환
    logger.info(f"API 요청 수신: intro_no={intro_no}")

    logger.info("데이터베이스 연결 시도")
    connection = get_oracle_connection()
    if not connection:
        logger.error("데이터베이스 연결 실패")
        add_self_intro_status = "idle"  # 상태를 idle로 초기화
        raise HTTPException(status_code=500, detail="데이터베이스 연결 실패")
    logger.info("데이터베이스 연결 성공")

    try:
        cursor = connection.cursor()
        logger.info("커서 생성 완료")

        # 자기소개서 내용 및 제목 조회
        logger.info(f"SELF_INTRODUCE 테이블에서 intro_no={intro_no} 데이터 조회 중")
        cursor.execute(
            "SELECT INTRO_CONTENTS, INTRO_TITLE FROM SELF_INTRODUCE WHERE INTRO_NO LIKE :pattern ORDER BY INTRO_NO DESC",
            {"pattern": f"{intro_no}%"}
        )
        results = cursor.fetchall()

        if not results:
            logger.warning(f"intro_no={intro_no}에 해당하는 자기소개서를 찾을 수 없습니다.")
            add_self_intro_status = "idle"  # 상태를 idle로 초기화
            raise HTTPException(status_code=404, detail="자기소개서를 찾을 수 없습니다.")

        # 최신 intro_no를 기준으로 새로운 번호 생성
        latest_intro_no = results[0][0]  # 가장 최신의 intro_no
        logger.info(f"가장 최신 intro_no={latest_intro_no}에서 새로운 번호 생성 시작")

        # `_번호`가 이미 있는지 확인
        if "_" in latest_intro_no:
            base_intro_no, current_suffix = latest_intro_no.rsplit("_", 1)
            if current_suffix.isdigit():
                new_suffix = int(current_suffix) + 1
                new_intro_no = f"{base_intro_no}_{new_suffix}"
            else:
                new_intro_no = f"{latest_intro_no}_1"  # 숫자가 아니면 _1 추가
        else:
            new_intro_no = f"{latest_intro_no}_1"  # 처음 `_1` 추가

        logger.info(f"새로운 intro_no 생성: {new_intro_no}")

        # 최신 자기소개서 내용과 제목 가져오기
        intro_contents, intro_title = results[0][1], results[0][2]
        logger.info(f"조회된 자기소개서 내용: {intro_contents[:100]}...")  # 너무 긴 내용은 자르기

        # OpenAI API 호출
        logger.info("OpenAI API를 이용해 첨삭 및 피드백 생성 요청")
        processed_content = process_self_introduction(intro_contents)
        if not processed_content:
            logger.error("OpenAI API 호출 실패")
            add_self_intro_status = "idle"  # 상태를 idle로 초기화
            raise HTTPException(status_code=500, detail="OpenAI API 호출 실패")

        # 첨삭된 내용 및 피드백 분리
        logger.info("OpenAI 응답에서 첨삭된 내용과 피드백 분리 중")
        split_index = processed_content.find("피드백:")
        if split_index == -1:
            logger.error(f"OpenAI 응답에서 첨삭 내용과 피드백을 분리할 수 없습니다: {processed_content}")
            add_self_intro_status = "idle"  # 상태를 idle로 초기화
            raise HTTPException(status_code=500, detail="첨삭 및 피드백 분리 실패")

        updated_content = processed_content[:split_index].strip()
        feedback = processed_content[split_index + 4:].strip()
        logger.info(f"첨삭된 내용 및 피드백 분리 성공: 첨삭된 내용 길이={len(updated_content)}, 피드백 길이={len(feedback)}")

        # 제목에 '(첨삭)' 추가
        if "(첨삭)" not in intro_title:
            intro_title += " (첨삭)"
            logger.info(f"제목에 '(첨삭)' 추가됨: {intro_title}")

        # DB 업데이트
        logger.info(f"SELF_INTRODUCE 테이블 업데이트: intro_no={new_intro_no}")
        current_timestamp = datetime.now()
        cursor.execute(
            """
            INSERT INTO SELF_INTRODUCE (
                INTRO_NO, INTRO_CONTENTS, INTRO_TITLE, INTRO_IS_EDITED, 
                INTRO_FEEDBACK, INTRO_DATE
            )
            VALUES (
                :new_intro_no, :updated_content, :intro_title, 'Y', 
                :feedback, :intro_date
            )
            """,
            {
                "new_intro_no": new_intro_no,
                "updated_content": updated_content,
                "intro_title": intro_title,
                "feedback": feedback,
                "intro_date": current_timestamp,
            }
        )

        connection.commit()
        logger.info(f"자기소개서 업데이트 성공: intro_no={new_intro_no}")
        add_self_intro_status = "complete"  # 요청 완료 후 상태를 "complete"로 설정

        return {
            "status": "success",
            "message": "자기소개서가 성공적으로 업데이트되었습니다.",
            "intro_no": new_intro_no
        }
    except Exception as e:
        logger.error(f"요청 처리 중 오류 발생: {e}")
        connection.rollback()
        add_self_intro_status = "idle"  # 상태를 idle로 초기화
        raise HTTPException(status_code=500, detail=f"요청 처리 중 오류 발생: {str(e)}")
    finally:
        logger.info("데이터베이스 연결 해제")
        connection.close()


@router.get("/status")
async def get_status():
    """
    현재 작업 상태를 반환하는 API.
    - 상태: True (작업 중), False (작업 대기)
    """
    global add_self_intro_status
    return {"status": add_self_intro_status}
