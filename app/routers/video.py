# # from fastapi import APIRouter, WebSocket
# # import cv2
# # import os
# # from threading import Thread
# #
# # router = APIRouter()
# #
# # # 경로 설정
# # BASE_PATH = "C:/JOBISIMG"
# # VIDEO_PATH = os.path.join(BASE_PATH, "video")
# #
# # # 폴더 생성
# # os.makedirs(VIDEO_PATH, exist_ok=True)
# #
# # # 녹화 상태
# # is_recording = False
# #
# #
# # def record_video(video_filename, duration):
# #     """카메라 영상 녹화 함수"""
# #     global is_recording
# #
# #     cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
# #     fourcc = cv2.VideoWriter_fourcc(*"mp4v")
# #     out = cv2.VideoWriter(video_filename, fourcc, 20.0, (640, 480))
# #
# #     if not cap.isOpened():
# #         print("Error: Cannot open camera.")
# #         return
# #
# #     is_recording = True
# #     print(f"Recording video for {duration} seconds...")
# #
# #     for _ in range(int(duration * 20)):  # 20 FPS 기준
# #         if not is_recording:
# #             break
# #         ret, frame = cap.read()
# #         if ret:
# #             frame = cv2.flip(frame, 1)  # 좌우 반전
# #             out.write(frame)
# #
# #     cap.release()
# #     out.release()
# #     print(f"Video saved to {video_filename}")
# #
# #
# # @router.websocket("/record_video")
# # async def video_recording_endpoint(websocket: WebSocket):
# #     global is_recording
# #     await websocket.accept()
# #
# #     try:
# #         data = await websocket.receive_json()
# #         duration = data.get("duration", 20)
# #         uuid = data.get("uuid")
# #
# #         if not uuid:
# #             await websocket.send_text("Missing 'uuid'.")
# #             await websocket.close()
# #             return
# #
# #         video_filename = os.path.join(VIDEO_PATH, f"{uuid}_recorded.mp4")
# #
# #         # 녹화 스레드 시작
# #         video_thread = Thread(target=record_video, args=(video_filename, duration))
# #         video_thread.start()
# #
# #         await websocket.send_text(f"Video recording started for {duration} seconds.")
# #         video_thread.join()
# #
# #         await websocket.send_text(f"Video recording finished. File saved to {video_filename}")
# #     except Exception as e:
# #         print(f"Error during video recording: {e}")
# #     finally:
# #         is_recording = False
# import cv2
# import os
# from moviepy.editor import VideoFileClip
#
# def record_video(save_path, duration=10, fps=20, resolution=(640, 480)):
#     """
#     캠 화면을 녹화하는 함수.
#     Args:
#         save_path (str): 녹화 영상이 저장될 경로 (mp4 형식).
#         duration (int): 녹화 시간 (초).
#         fps (int): 초당 프레임 수.
#         resolution (tuple): 영상 해상도 (가로, 세로).
#     """
#     # 비디오 캡처 객체 초기화
#     cap = cv2.VideoCapture(0)
#     cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
#     cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
#
#     if not cap.isOpened():
#         print("캠을 열 수 없습니다.")
#         return
#
#     # 임시 AVI 파일로 저장 (나중에 MP4로 변환)
#     temp_avi_path = save_path.replace('.mp4', '.avi')
#     fourcc = cv2.VideoWriter_fourcc(*'XVID')
#     out = cv2.VideoWriter(temp_avi_path, fourcc, fps, resolution)
#
#     print("녹화를 시작합니다. ESC 키를 눌러 종료하거나 {}초 뒤 자동 종료됩니다.".format(duration))
#     frame_count = 0
#     max_frames = duration * fps
#
#     while cap.isOpened():
#         ret, frame = cap.read()
#         if not ret:
#             print("프레임을 읽을 수 없습니다.")
#             break
#
#         out.write(frame)
#         cv2.imshow('Recording', frame)
#
#         # ESC 키로 종료 가능
#         if cv2.waitKey(1) & 0xFF == 27:
#             print("녹화를 종료합니다.")
#             break
#
#         frame_count += 1
#         if frame_count >= max_frames:
#             print("자동으로 녹화를 종료합니다.")
#             break
#
#     # 자원 해제
#     cap.release()
#     out.release()
#     cv2.destroyAllWindows()
#
#     # AVI 파일을 MP4로 변환
#     try:
#         clip = VideoFileClip(temp_avi_path)
#         clip.write_videofile(save_path, codec="libx264", audio=False)
#         os.remove(temp_avi_path)
#         print(f"녹화가 완료되었습니다. 파일이 저장되었습니다: {save_path}")
#     except Exception as e:
#         print("MP4 변환 중 오류가 발생했습니다:", e)
#
# # 저장 경로 설정
# output_dir = r"C:\JOBISIMG\video"
# os.makedirs(output_dir, exist_ok=True)
# output_file = os.path.join(output_dir, "recorded_video.mp4")
#
# # 캠 녹화 실행 (10초간 녹화)
# record_video(output_file, duration=10)

import cv2

# 웹캠에서 동영상 캡쳐
cap = cv2.VideoCapture(0)

# 녹화할 동영상의 코덱 설정
fourcc = cv2.VideoWriter_fourcc(*'XVID')

# 동영상 녹화를 위한 객체 생성
out = cv2.VideoWriter('output.avi', fourcc, 20.0, (640, 480))

while True:
    # 프레임 읽기
    ret, frame = cap.read()

    if ret:
        # 프레임 출력
        cv2.imshow('frame', frame)

        # 녹화된 동영상 저장
        out.write(frame)

    # 'q' 키를 누르면 종료
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 자원 해제
cap.release()
out.release()
cv2.destroyAllWindows()
