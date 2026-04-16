# test_crop_ocr.py
import cv2
import numpy as np

IMG = r"out\page_69.png"

# TODO: replace these after you find the correct box once
X0, Y0, X1, Y1 = 100, 100, 200, 160

def ocr_digits_only(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    bw = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 11
    )

    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 80))
    h = cv2.morphologyEx(bw, cv2.MORPH_OPEN, h_kernel, iterations=1)
    v = cv2.morphologyEx(bw, cv2.MORPH_OPEN, v_kernel, iterations=1)
    lines = cv2.bitwise_or(h, v)

    bw2 = cv2.bitwise_and(bw, cv2.bitwise_not(lines))
    bw2 = cv2.morphologyEx(
        bw2, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        iterations=1
    )

    # Use OpenCV OCR-free approach first: connected components digits only
    # If you want Tesseract/Paddle, plug it here.
    return bw2

img = cv2.imread(IMG)
if img is None:
    raise RuntimeError(f"Cannot read image: {IMG}")

cell = img[Y0:Y1, X0:X1].copy()

# Trim left side to remove vertical border
w = cell.shape[1]
cell = cell[:, int(w * 0.15):]

bw = ocr_digits_only(cell)

cv2.imwrite(r"out\debug_cell.png", cell)
cv2.imwrite(r"out\debug_cell_bw.png", bw)

print("Wrote out\\debug_cell.png and out\\debug_cell_bw.png")