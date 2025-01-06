from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import cv2

app = FastAPI()

# 카메라 스트림 열기
camera = cv2.VideoCapture(0)  # 0은 기본 카메라를 의미

def generate_frames():
    while True:
        success, frame = camera.read()  # 카메라에서 프레임 읽기
        if not success:
            break

        # 좌우 반전 처리
        flipped_frame = cv2.flip(frame, 1)  # 1은 좌우 반전, 0은 상하 반전

        # 프레임을 JPEG 형식으로 인코딩
        _, buffer = cv2.imencode(".jpg", flipped_frame)
        frame_bytes = buffer.tobytes()

        # HTTP 스트리밍 응답에 프레임 전달
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
# uuid 자소서넘버 회차번호 > 넘겨야하고
# 폴더 uuid_자소서번호_회차번호
# mp3 mp4 각각 저장