import logging
from fastapi import APIRouter, HTTPException
from app.utils.db_connection import get_oracle_connection
import openai
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel
import os
import re

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
def generate_questions_and_answers(prompt, model="gpt-4-turbo-2024-04-09"):
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
                INTERVIEW_ROUND
            )
            VALUES (
                :int_id,
                :intro_no,
                :int_date,
                :int_d_date,
                :int_is_deleted,
                :interview_round
            )
            """,
            {
                "int_id": int_id,
                "intro_no": intro_no,
                "int_date": current_timestamp,
                "int_d_date": None,
                "int_is_deleted": 'N',
                "interview_round": RoundId
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
        **질문**: '내용' 줄바꿈 **답변**: '내용' 형식으로 해주세요.
        자기소개서: {intro_contents}
        """
        ai_response = generate_questions_and_answers(prompt)
        if not ai_response:
            logger.error("OpenAI API 호출 실패")
            raise HTTPException(status_code=500, detail="OpenAI API 호출 실패")

        # 질문-답변 추출
        qa_pattern = r"(?:\s*\**\s*\d*\s*질문\s*\**\s*\d*\**)?\s*:\s*(.+?)\n(?:\s*\**\s*\d*\s*답변\s*\**\s*\d*\**)?\s*:\s*(.+?)(?=\n(?:\s*\**\s*\d*\s*질문\s*|\Z))"


        matches = re.findall(qa_pattern, ai_response, re.DOTALL)

        if not matches:
            logger.error(f"OpenAI API 응답 데이터가 예상된 형식이 아닙니다: {ai_response}")
            raise HTTPException(status_code=500, detail="질문과 답변을 추출하지 못했습니다.")

        for index, (question, answer) in enumerate(matches, start=1):
            question = question.strip()
            answer = answer.strip()
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')

            iq_no = f"{timestamp}_{intro_no}_{index}"
            logger.info(f"저장 중인 질문: {question}, 답변: {answer}, ID: {iq_no}, INTERVIEW_ROUND: {RoundId}")
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
                    "question": question,
                    "answer": answer,
                    "interview_round": RoundId
                }
            )

        connection.commit()
        logger.info("모든 데이터가 성공적으로 커밋되었습니다.")

        addInterviewStatus = "complete"
        logger.info(f"addInterviewStatus 상태가 'complete'로 변경되었습니다.")

        # RoundId를 응답에 포함
        return {
            "status": "success",
            "message": "예상 질문 및 답변이 성공적으로 저장되었습니다.",
            "RoundId": RoundId,
            "INT_ID" : int_id
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

@router.get("/interview/data")
async def get_interview_data(intro_no: str, round: int):
    connection = get_oracle_connection()
    if not connection:
        raise HTTPException(status_code=500, detail="데이터베이스 연결 실패")

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT INT_ID, INTRO_NO, INTERVIEW_ROUND 
            FROM INTERVIEW 
            WHERE INTRO_NO = :intro_no AND INTERVIEW_ROUND = :round
            """,
            {"intro_no": intro_no, "round": round},
        )
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="인터뷰 데이터를 찾을 수 없습니다.")

        interview = {
            "INT_ID": result[0],
            "INTRO_NO": result[1],
            "INTERVIEW_ROUND": result[2],
        }
        return {"interview": interview}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connection.close()


@router.get("/interview/questions")
async def get_question_set(intro_no: str, round: int):
    connection = get_oracle_connection()
    if not connection:
        raise HTTPException(status_code=500, detail="데이터베이스 연결 실패")

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT IQ_NO, INTRO_NO, INTERVIEW_QUESTIONS, SAMPLE_ANSWER, INTERVIEW_ROUND 
            FROM INTERVIEW_QUESTION_SET 
            WHERE INTRO_NO = :intro_no AND INTERVIEW_ROUND = :round
            ORDER BY IQ_NO ASC
            """,
            {"intro_no": intro_no, "round": round},
        )
        results = cursor.fetchall()
        questions = [
            {
                "IQ_NO": row[0],
                "INTRO_NO": row[1],
                "INTERVIEW_QUESTIONS": row[2],
                "SAMPLE_ANSWER": row[3],
                "INTERVIEW_ROUND": row[4],
            }
            for row in results
        ]
        return {"questions": questions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connection.close()


