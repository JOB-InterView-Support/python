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



# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# OpenAI API 키 설정
# 환경 변수 가져오기
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
        logger.info(f"OpenAI API 응답: {content}")  # 응답 내용을 로깅
        print(f"OpenAI API 응답: {content}")  # 응답 내용을 콘솔에 출력
        return content
    except openai.error.OpenAIError as e:
        logger.error(f"OpenAI API 호출 중 오류 발생: {e}")
        return None


@router.post("/addQuestions")
async def create_interview_questions(request: AddQuestionsRequest):
    """
    자기소개서를 기반으로 예상 면접 질문 및 답변 생성 후 DB에 저장
    """
    intro_no = request.intro_no  # Pydantic 모델로 받은 데이터 사용
    logger.info(f"요청받은 자기소개서 번호: {intro_no}")

    # 데이터베이스 연결 확인
    connection = get_oracle_connection()
    if not connection:
        logger.error("데이터베이스 연결 실패")
        raise HTTPException(status_code=500, detail="데이터베이스 연결 실패")

    try:
        cursor = connection.cursor()

        # 자기소개서 내용 조회
        logger.info(f"intro_no: {intro_no}에 해당하는 자기소개서 내용 조회 시도")
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
        **질문** : '내용', **답변** : '내용' 형식으로 해주세요.
        자기소개서: {intro_contents}
        """
        logger.info("OpenAI API 호출 시도")
        ai_response = generate_questions_and_answers(prompt)
        if not ai_response:
            logger.error("OpenAI API 호출 실패")
            raise HTTPException(status_code=500, detail="OpenAI API 호출 실패")

        # 응답 데이터 파싱
        logger.info("OpenAI 응답 데이터 파싱 시작")
        # questions_and_answers = ai_response.split("\n")

        # 질문/답변 추출을 위한 정규식 정의
        qa_pattern = r"\*\*질문\s\d+\*\*\s:\s(.+?)\n\*\*답변\s\d+\*\*\s:\s(.+?)(?=\n\*\*질문|\Z)"

        matches = re.findall(qa_pattern, ai_response, re.DOTALL)  # 정규식으로 질문과 답변 추출
        for index, (question, answer) in enumerate(matches, start=1):
            question = question.strip()  # 질문 내용에서 공백 제거
            answer = answer.strip()  # 답변 내용에서 공백 제거
            current_date = datetime.utcnow().strftime('%Y%m%d')  # 현재 날짜를 YYYYMMDD 형식으로 가져오기
            iq_no = f"{current_date}_{intro_no}_{index}"  # 날짜_introNo_index 형식
            logger.info(f"저장 중인 질문: {question}, 답변: {answer}, ID: {iq_no}")
            cursor.execute(
                """
                INSERT INTO INTERVIEW_QUESTION_SET (IQ_NO, INTRO_NO, INTERVIEW_QUESTIONS, SAMPLE_ANSWER)
                VALUES (:iq_no, :intro_no, :question, :answer)
                """,
                {"iq_no": iq_no, "intro_no": intro_no, "question": question, "answer": answer}
            )

        connection.commit()
        logger.info("모든 질문과 답안이 성공적으로 데이터베이스에 저장되었습니다.")
        return {"status": "success", "message": "예상 질문 및 답변이 성공적으로 저장되었습니다."}
    except Exception as e:
        logger.error(f"요청 처리 중 오류 발생: {e}")
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"요청 처리 중 오류 발생: {str(e)}")
    finally:
        connection.close()
