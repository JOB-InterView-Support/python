from fastapi import APIRouter, Form
import os

router = APIRouter()

@router.post("/analysis")
async def analyze_audio(audioFilename: str = Form(...), introNo: str = Form(...), roundId: str = Form(...), intId: str = Form(...)):
    audio_path = f'C:\\JOBISIMG\\AUDIO\\{audioFilename}'
    audio_exists = os.path.exists(audio_path)
    print(f"음성 파일 존재 Audio File: {audioFilename} Exists: {audio_exists}")


    return {"audioFilename": audioFilename, "exists": audio_exists, "introNo": introNo, "roundId": roundId, "intId": intId}
