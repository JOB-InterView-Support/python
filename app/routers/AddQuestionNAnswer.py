import logging
from fastapi import APIRouter, HTTPException
from app.utils.db_connection import get_oracle_connection
import openai
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel
import pandas as pd
import os
import re  # 오류 원인 해결을 위해 추가
import uuid

# .env 파일 로드
load_dotenv()

# 라우터 생성
router = APIRouter()

# 전역 변수 정의
addInterviewStatus = False
RoundId = 0  # 회차 ID 기본값

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# OpenAI API 키 설정
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logger.error("OpenAI API Key가 로드되지 않았습니다.")
    raise HTTPException(status_code=500, detail="OpenAI API Key가 설정되지 않았습니다.")


# 요청 데이터를 위한 Pydantic 모델 정의
class AddQuestionsRequest(BaseModel):
    intro_no: str


# OpenAI 프롬프트 처리
def generate_questions_and_answers(prompt, model="gpt-3.5-turbo-1106"):
    try:
        if not openai_api_key:
            logger.error("OpenAI API Key가 설정되지 않았습니다.")
            raise HTTPException(status_code=500, detail="OpenAI API Key가 설정되지 않았습니다.")

        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": "당신은 면접 준비를 전문적으로 도와주는 AI입니다."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message["content"]
        logger.info(f"OpenAI API 응답: {content}")
        return content
    except openai.error.OpenAIError as e:
        logger.error(f"OpenAI API 호출 중 오류 발생: {e}")
        return None
# OpenAI 응답 클리닝 함수
def clean_ai_response(content):

    cleaned_content = re.sub(r"^.*과 모범 답안:\s*", "", content, flags=re.DOTALL)
    return cleaned_content.strip()

@router.post("/addQuestions")
async def create_interview_questions(request: AddQuestionsRequest):
    global addInterviewStatus, RoundId
    addInterviewStatus = "ing"
    logger.info(f"addInterviewStatus 상태가 'ing'로 변경되었습니다.")

    intro_no = request.intro_no
    logger.info(f"요청받은 자기소개서 번호: {intro_no}")

    connection = get_oracle_connection()
    if not connection:
        logger.error("데이터베이스 연결 실패")
        raise HTTPException(status_code=500, detail="데이터베이스 연결 실패")

    csv_path = None

    try:
        cursor = connection.cursor()

        # intro_no에 해당하는 데이터가 interview 테이블에 있는지 확인
        cursor.execute("SELECT MAX(INTERVIEW_ROUND) FROM interview WHERE INTRO_NO = :intro_no", {"intro_no": intro_no})
        result = cursor.fetchone()
        last_round = result[0] if result and result[0] is not None else 0

        # 새로운 INTERVIEW_ROUND 계산
        RoundId = last_round + 1
        logger.info(f"새로운 INTERVIEW_ROUND: {RoundId}")
        parsed_intro_no = "INTRO_" + intro_no[6:]

        # INTERVIEW 테이블에 데이터 삽입
        int_id = f"{parsed_intro_no}_{RoundId}"  # INT_ID 생성
        current_timestamp = datetime.now()  # 현재 타임스탬프
        cursor.execute(
            """
            INSERT INTO INTERVIEW (
                INT_ID,
                INTRO_NO,
                INT_DATE,
                INT_D_DATE,
                INT_IS_DELETED,
                INTERVIEW_ROUND,
                CONPLETE_STATUS
            )
            VALUES (
                :int_id,
                :intro_no,
                :int_date,
                :int_d_date,
                :int_is_deleted,
                :interview_round,
                :complete_status
            )
            """,
            {
                "int_id": int_id,
                "intro_no": intro_no,
                "int_date": current_timestamp,
                "int_d_date": None,
                "int_is_deleted": 'N',
                "interview_round": RoundId,
                "complete_status": 'N'
            }
        )
        logger.info(f"INTERVIEW 테이블 데이터 삽입 완료: INT_ID={int_id}, INTRO_NO={intro_no}")

        # 자기소개서 내용 조회
        cursor.execute("SELECT intro_contents FROM self_introduce WHERE intro_no = :intro_no", {"intro_no": intro_no})
        result = cursor.fetchone()
        if not result:
            logger.warning(f"자기소개서를 찾을 수 없습니다. intro_no: {intro_no}")
            raise HTTPException(status_code=404, detail="자기소개서를 찾을 수 없습니다.")

        intro_contents = result[0]
        logger.info(f"조회된 자기소개서 내용: {intro_contents[:100]}...")

        # OpenAI API 호출
        prompt = f"""
        다음은 제가 작성한 자기소개서입니다. 이 자기소개서를 바탕으로 면접에서 나올 가능성이 높은 질문 5개와 해당 질문에 대한 모범 답안을 작성해주세요. 
        
        반드시 아래 형식을 따라:
        
        **질문**: 
        (질문 내용)
        
        **답변**: 
        (답변 내용)
        
        자기소개서: {intro_contents}
        """
        ai_response = generate_questions_and_answers(prompt)
        if not ai_response:
            logger.error("OpenAI API 호출 실패")
            raise HTTPException(status_code=500, detail="OpenAI API 호출 실패")

        # 불필요한 텍스트 제거
        ai_response = clean_ai_response(ai_response)

        # 질문-답변 추출
        qa_pattern = (
            r"(?:"
            r"\d+\.\s*\*\*질문\*\*"  # "1. **질문**" 형태
            r"|\*\*질문\s*\d+\*\*"  # "**질문 1**" 형태
            r"|\s*\*\*질문\*\*"  # "**질문**" 형태
            r"|\s*질문\s*\d*[:\-]?"  # "질문 1:" 또는 "질문:" 형태
            r"|\*\*질문\s*\d+\*\*:\s*.*?"  # "**질문 1**: 내용" 형태
            r"|\*\*질문\s*.*?\*\*:"  # "**질문 ...**: 내용" (질문 번호가 없을 경우)
            r")\s*:\s*(.+?)\s*"
            r"(?:"
            r"\*\*답변\*\*"  # "**답변**" 형태
            r"|\s*답변[:\-]?"  # "답변:" 형태
            r"|\*\*답변\s*\d+\*\*:?.*?"  # "**답변 1**: 내용" 형태
            r"|\*\*답변\s*.*?\*\*:"  # "**답변 ...**: 내용" (답변 번호가 없을 경우)
            r")\s*:\s*(.+?)"
            r"(?=\n(?:"
            r"\d+\.\s*\*\*질문\*\*"  # 다음 "1. **질문**" 형태
            r"|\*\*질문\s*\d+\*\*"  # 다음 "**질문 1**" 형태
            r"|\s*\*\*질문\*\*"  # 다음 "**질문**" 형태
            r"|\s*질문\s*\d*[:\-]?"  # 다음 "질문 1:" 형태
            r"|\*\*질문\s*.*?\*\*:"  # 다음 "**질문 ...**: 내용"
            r")|\Z)"
        )
        matches = re.findall(qa_pattern, ai_response, re.DOTALL)

        logger.info(f"질문-답변 매치 개수: {len(matches)}")
        if len(matches) != 5:
            logger.error(f"추출된 질문/답변 수가 예상과 다릅니다: {len(matches)}")
            raise HTTPException(status_code=500, detail="질문과 답변 추출 중 오류가 발생했습니다.")

        # CSV 파일 저장
        data = [{"질문": question.strip(), "답변": answer.strip()} for question, answer in matches]
        csv_path = f"interview_questions_{intro_no}.csv"
        pd.DataFrame(data).to_csv(csv_path, index=False, encoding="utf-8-sig")
        logger.info(f"질문/답변 데이터를 CSV 파일로 저장 완료: {csv_path}")

        # CSV 데이터를 DB로 삽입
        for row in data:
            iq_no = f"{uuid.uuid4()}_{intro_no}"
            cursor.execute(
                """
                INSERT INTO INTERVIEW_QUESTION_SET (
                    IQ_NO,
                    INTRO_NO,
                    INTERVIEW_QUESTIONS,
                    SAMPLE_ANSWER,
                    INTERVIEW_ROUND
                )
                VALUES (
                    :iq_no,
                    :intro_no,
                    :question,
                    :answer,
                    :interview_round
                )
                """,
                {
                    "iq_no": iq_no,
                    "intro_no": intro_no,
                    "question": row["질문"],
                    "answer": row["답변"],
                    "interview_round": RoundId
                }
            )

        connection.commit()
        logger.info("CSV 데이터를 DB에 성공적으로 삽입했습니다.")

        # CSV 파일 삭제
        if csv_path and os.path.exists(csv_path):
            os.remove(csv_path)
            logger.info(f"CSV 파일 삭제 완료: {csv_path}")

        addInterviewStatus = "complete"
        logger.info(f"addInterviewStatus 상태가 'complete'로 변경되었습니다.")

        return {
            "status": "success",
            "message": "예상 질문 및 답변이 성공적으로 저장되었습니다.",
            "RoundId": RoundId,
            "INT_ID": int_id
        }
    except Exception as e:
        logger.error(f"요청 처리 중 오류 발생: {e}")
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"요청 처리 중 오류 발생: {str(e)}")
    finally:
        connection.close()


@router.get("/status")
async def get_status():
    global addInterviewStatus

    current_status = "complete" if addInterviewStatus == "complete" else "in_progress"

    if addInterviewStatus == "complete":
        addInterviewStatus = False
        logger.info("addInterviewStatus 상태가 'False'로 초기화되었습니다.")

    return {"status": current_status}
