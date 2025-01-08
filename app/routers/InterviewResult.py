from fastapi import APIRouter, HTTPException
from app.utils.db_connection import get_oracle_connection

router = APIRouter()

@router.get("/compare_self_introduce_interview/{uuid}")
async def compare_self_introduce_interview_with_uuid(uuid: str):
    try:
        connection = get_oracle_connection()
        cursor = connection.cursor()

        query = """
            SELECT si.INTRO_NO, si.UUID, si.INTRO_TITLE, 
                   CASE 
                       WHEN i.CONPLETE_STATUS = 'Y' THEN 'Y'
                       WHEN i.CONPLETE_STATUS = 'N' THEN 'N'
                   END AS STATUS
            FROM C##SS.SELF_INTRODUCE si
            INNER JOIN C##SS.INTERVIEW i 
            ON si.INTRO_NO = i.INTRO_NO
            WHERE si.INTRO_IS_DELETED = 'N' AND si.UUID = :uuid
        """
        print(f"Executing Query: {query}")
        print(f"UUID: {uuid}")

        cursor.execute(query, {"uuid": uuid})
        result = [
            {
                "intro_no": row[0],
                "uuid": row[1],
                "intro_title": row[2],
                "status": row[3]  # Y 또는 N
            }
            for row in cursor.fetchall()
        ]

        print(f"Query Result: {result}")

        cursor.close()
        connection.close()

        if not result:
            return {"message": "해당 UUID에 대한 기록이 없습니다."}

        return result

    except Exception as e:
        print(f"DB Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"DB Error: {str(e)}")
