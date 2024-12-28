from fastapi import APIRouter, HTTPException
from pathlib import Path
import base64

router = APIRouter()

@router.get("/image/{uuid}")
async def get_face_id_image(uuid: str):
    face_id_folder = Path("C:/JOBISIMG/FACEID")
    print(f"Searching for files in: {face_id_folder}")  # 디버깅
    print(f"Looking for files starting with UUID: {uuid}")  # 디버깅

    # UUID로 시작하는 파일 필터링
    files = sorted(
        face_id_folder.glob(f"{uuid}*"),
        key=lambda x: x.stat().st_mtime,  # 수정 시간 기준 정렬
        reverse=True,  # 최신순
    )

    if not files:
        print(f"No matching files found for pattern: {face_id_folder}\\{uuid}*")  # 디버깅
        raise HTTPException(status_code=404, detail="UUID로 시작하는 파일이 없습니다.")

    latest_file = files[0]
    print(f"Latest file found: {latest_file}")  # 디버깅

    # 파일 읽기 및 Base64 인코딩
    with open(latest_file, "rb") as f:
        image_data = f.read()
        encoded_image = base64.b64encode(image_data).decode("utf-8")

    return {"image": encoded_image}