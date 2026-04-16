from paddleocr import PaddleOCR
import cv2

ocr = PaddleOCR(use_angle_cls=True, lang='en')

img_path = "test_page.png"  # export one PDF page as image first

result = ocr.ocr(img_path, cls=True)

for line in result[0]:
    print(line[1][0])