from PIL import ImageFont, ImageDraw, Image
import numpy as np
import cv2

FONT_SIZE = 30

def draw_text_korean(img, text, position, font_size=FONT_SIZE, color=(0, 255, 255)):
    """
    OpenCV 이미지를 Pillow로 변환하여 기본 폰트를 사용해 한글 텍스트를 추가.
    """
    # OpenCV 이미지를 Pillow Image로 변환
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)

    # 기본 폰트 로드
    font = ImageFont.load_default()

    # 텍스트 추가
    draw.text(position, text, font=font, fill=color)

    # Pillow 이미지를 OpenCV 이미지로 변환
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
