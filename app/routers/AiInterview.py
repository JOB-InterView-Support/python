from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import cv2

router = APIRouter()

# OpenCV 카메라 초기화
camera = cv2.VideoCapture(0)  # 0은 기본 카메라를 의미

def generate_frames():
    """카메라 프레임을 생성하는 함수"""
    while True:
        success, frame = camera.read()
        if not success:
            break

        # 프레임을 좌우 반전
        flipped_frame = cv2.flip(frame, 1)

        # 프레임을 JPEG로 인코딩
        _, buffer = cv2.imencode(".jpg", flipped_frame)
        frame_bytes = buffer.tobytes()

        # HTTP 스트리밍 응답에 프레임 전달
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )

@router.post("/setting")
async def ai_interview_setting(request: Request):
    """AI Interview 설정 엔드포인트"""
    data = await request.json()
    intro_no = data.get("intro_no")
    round_id = data.get("round")
    uuid = data.get("uuid")

    if not intro_no or not round_id or not uuid:
        raise HTTPException(status_code=400, detail="Missing required parameters")

    print(f"Intro No: {intro_no}, Round ID: {round_id}, UUID: {uuid}")

    return {"status": "success", "message": "Settings applied successfully"}

@router.get("/video_feed")
def video_feed():
    """카메라 스트리밍 엔드포인트"""
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
