from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from ..utils.db_connection import get_oracle_connection
import cx_Oracle

router = APIRouter()

class InterviewResultRequest(BaseModel):
    uuid: str

class InterviewInfo(BaseModel):
    INT_ID: str
    INTRO_NO: str
    INT_DATE: str
    INT_D_DATE: Optional[str] = None
    INT_IS_DELETED: str
    INTERVIEW_ROUND: str
    CONPLETE_STATUS: str
    INTRO_TITLE: str  # 자기소개서 제목 추가

@router.post("/getResult")
async def get_interview_result(request: Request, data: InterviewResultRequest):
    uuid = data.uuid
    print(f"Received UUID: {uuid}")

    connection = get_oracle_connection()
    if not connection:
        return {"message": "Database connection failed"}

    try:
        cursor = connection.cursor()
        query_intro = """
            SELECT s.INTRO_NO, s.INTRO_IS_DELETED, s.INTRO_TITLE
            FROM SELF_INTRODUCE s
            WHERE s.UUID = :uuid AND s.INTRO_IS_DELETED = 'N'
        """
        cursor.execute(query_intro, [uuid])
        intros = cursor.fetchall()
        print("자소서 테이블 조회 : ", intros)

        valid_intros = {intro[0]: intro[2] for intro in intros if intro[1] != 'Y'}  # INTRO_NO를 key로, INTRO_TITLE을 value로 사용

        if not valid_intros:
            return {"message": "등록된 자기소개서가 없습니다."}

        interviews = []
        for intro_no, intro_title in valid_intros.items():
            cursor.execute("""
                SELECT INT_ID, INTRO_NO, INT_DATE, INT_D_DATE, INT_IS_DELETED, INTERVIEW_ROUND, CONPLETE_STATUS
                FROM INTERVIEW 
                WHERE INTRO_NO = :intro_no AND INT_IS_DELETED = 'N'
                ORDER BY INT_DATE DESC 
            """, {'intro_no': intro_no})
            interview_data = cursor.fetchall()
            print("인터뷰 테이블 조회 결과 : ", interview_data)

            for item in interview_data:
                interviews.append({
                    "INT_ID": item[0],
                    "INTRO_NO": item[1],
                    "INT_DATE": item[2],
                    "INT_D_DATE": item[3],
                    "INT_IS_DELETED": item[4],
                    "INTERVIEW_ROUND": item[5],
                    "CONPLETE_STATUS": item[6],
                    "INTRO_TITLE": intro_title  # 자기소개서 제목도 포함
                })

        if not interviews:
            return {"message": "모의면접을 진행하지 않았습니다."}

        return {"interviews": interviews}
    finally:
        connection.close()


