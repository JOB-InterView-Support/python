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
# 폴더 uuid_intro_no_모의면접ID(intro_ro)_회차 >> 파이썬에서 > react > 파이썬(인경 영주)으로 // 파일명이 react에서 파이썬으로 이동
# mp3 mp4 각각 저장
# intro_no = 질문 가져오기
# intro_ro = 저장
#  = 회차
# 파일명 저장은 생각중
# aiinterview.py
# int_id를 받아서 화면 띄우기
# 카메라 마이크 선택창 및 테스트 그리고 시작버튼
# 바로 시작 or 페이지 넘어가서 할건지
# 원본녹화 및 음성녹음 (질문 안보이게)

# 1. 마이크 카메라 세팅 d
# 2. 시작버튼 누르면 세팅ui 사라지게 d
# 3. DB가서 공통질문("Y") , no > 예상질문 가져와서 타이머마다 뿌리기
# 4. 타이머 구현 d
# 5. mp3 mp4로 저장 > 이름은 uuid_intro_no_회차 d

