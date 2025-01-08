from fastapi import APIRouter, Form
import os

router = APIRouter()

@router.post("/analysis")
async def analyze_video(videoFilename: str = Form(...), introNo: str = Form(...), roundId: str = Form(...), intId: str = Form(...)):
    video_path = f'C:\\JOBISIMG\\VIDEO\\{videoFilename}'
    video_exists = os.path.exists(video_path)
    print(f"영상 파일 존재 Video File: {videoFilename} Exists: {video_exists}")
    return {"videoFilename": videoFilename, "exists": video_exists, "introNo": introNo, "roundId": roundId, "intId": intId}
