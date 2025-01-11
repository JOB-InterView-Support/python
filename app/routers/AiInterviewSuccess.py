from fastapi import APIRouter, HTTPException
from ..utils.db_connection import get_oracle_connection
import logging
from pydantic import BaseModel

router = APIRouter()

class StatusUpdateRequest(BaseModel):
    intId: str

@router.post("/changeStatus")
async def change_status(request_data: StatusUpdateRequest):
    int_id = request_data.intId
    print("인터뷰 데이터베이스 상태 업데이트 : ", int_id)
    connection = get_oracle_connection()
    if connection is None:
        raise HTTPException(status_code=500, detail="Database connection failed.")

    try:
        logging.info(f"Received intId: {int_id}")
        cursor = connection.cursor()
        update_query = """
        UPDATE INTERVIEW
        SET CONPLETE_STATUS = 'Y'
        WHERE INT_ID = :int_id
        """
        cursor.execute(update_query, {'int_id': int_id})
        connection.commit()

        logging.info(f"Status changed for intId {int_id}")
        return {"status": "success", "message": f"Status changed for intId {int_id}"}
    except Exception as e:
        logging.error(f"Error in changing status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error in processing the status change: {str(e)}")
    finally:
        cursor.close()
        connection.close()


