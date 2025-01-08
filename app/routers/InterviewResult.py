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
                       WHEN EXISTS (
                           SELECT 1 
                           FROM C##SS.INTERVIEW i 
                           WHERE i.INTRO_NO = si.INTRO_NO
                             AND i.CONPLETE_STATUS = 'Y'
                       ) THEN 'Y'
                       ELSE 'N'
                   END AS EXISTS_IN_INTERVIEW
            FROM C##SS.SELF_INTRODUCE si
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
                "exists_in_interview": row[3]
            }
            for row in cursor.fetchall()
        ]

        print(f"Query Result: {result}")

        cursor.close()
        connection.close()

        return result if result else []

    except Exception as e:
        print(f"DB Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"DB Error: {str(e)}")







