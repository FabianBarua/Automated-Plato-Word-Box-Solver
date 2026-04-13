from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING, List

import cv2
import numpy as np
import win32con
import win32gui
import win32ui
from PIL import Image

from ml.letter_classifier import LetterClassifier

if TYPE_CHECKING:
    from core.controller import AppController

from core.paths import SCREENSHOT_DIR
SCREENSHOT_DIR.mkdir(exist_ok=True)


class ImgProcessing:
    def __init__(self, controller: AppController) -> None:
        self.controller = controller
        self.classifier = LetterClassifier()
        self.contour_info_grid: list = []

        self.window_left: int = 0
        self.window_top: int = 0

        self.is_processing: bool = False
        self.img = None
        self.letters_info: List[tuple[int, int, str]] = []

        self.image_path = SCREENSHOT_DIR / "wordbox.png"

    # ── Pipeline ────────────────────────────────────────────────────

    def pipeline(self) -> None:
        app = self.controller.app
        app.is_scanning = True

        self._screenshot_window()
        self.img = cv2.imread(str(self.image_path))
        self._img_to_text()
        self._convert_to_letter_grid()

        app.is_scanning = False

    # ── Screenshot ──────────────────────────────────────────────────

    def _screenshot_window(self) -> None:
        hwnd = self.controller.app.get_mirror_hwnd()
        if not hwnd:
            return

        left, top = win32gui.ClientToScreen(hwnd, (0, 0))
        right, bottom = win32gui.ClientToScreen(hwnd, win32gui.GetClientRect(hwnd)[2:])

        self.window_left = left
        self.window_top = top

        width = right - left
        height = bottom - top

        hwnd_dc = win32gui.GetDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bitmap)
        save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

        bmpinfo = bitmap.GetInfo()
        bmpstr = bitmap.GetBitmapBits(True)
        image = Image.frombuffer(
            "RGB",
            (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
            bmpstr,
            "raw",
            "BGRX",
            0,
            1,
        )
        image.save(self.image_path)

    # ── Grid extraction (unchanged per user request) ────────────────

    def _get_grid_img(self):
        img = self.img.copy()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.threshold(blurred, 180, 255, cv2.THRESH_BINARY)[1]

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (8, 3))
        dilate = cv2.dilate(thresh, kernel, iterations=2)
        contours, _ = cv2.findContours(dilate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        padding = 5
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        H, W = self.img.shape[:2]

        mask = np.zeros(self.img.shape[:2], dtype=np.uint8)
        cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)

        grid_img = self.img.copy()
        grid_img[mask == 0] = 255
        return grid_img

    def _get_letter_contours(self):
        grid_img = self._get_grid_img()
        gray = cv2.cvtColor(grid_img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.threshold(blurred, 150, 255, cv2.THRESH_BINARY_INV)[1]

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (8, 3))
        dilate = cv2.dilate(thresh, kernel, iterations=2)
        contours, _ = cv2.findContours(dilate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours, grid_img

    # ── Letter image helpers ────────────────────────────────────────

    def _create_letter_square_img(self, img, contour, pad: int):
        x, y, w, h = cv2.boundingRect(contour)
        crop = img[y : y + h, x : x + w]
        size = max(w, h) + 2 * pad

        padded = np.ones((size, size, 3), dtype=np.uint8) * 255
        x_off = (size - w) // 2
        y_off = (size - h) // 2
        padded[y_off : y_off + h, x_off : x_off + w] = crop

        return padded, (x, y, w, h)

    def _preprocess_letter_img(self, letter_img):
        gray = cv2.cvtColor(letter_img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
        return thresh

    # ── OCR ─────────────────────────────────────────────────────────

    def _get_letter_text(self, letter_img) -> tuple[str, float]:
        letter_inv = cv2.bitwise_not(letter_img.copy())
        contours, _ = cv2.findContours(letter_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        letter_rgb = cv2.cvtColor(letter_img, cv2.COLOR_GRAY2RGB)

        if len(contours) > 1:
            contours = contours[::-1]
            characters = ""
            total_conf = 0.0
            for idx, cont in enumerate(contours):
                sub_img, _ = self._create_letter_square_img(letter_rgb, cont, 1)
                char, conf = self.classifier.read_letter(sub_img)
                if char == "l" and idx == 0:
                    char = "I"
                characters += char
                total_conf += conf
            return characters, round(total_conf / len(characters), 2)

        char, conf = self.classifier.read_letter(letter_rgb)
        return char, round(conf, 2)

    def _img_to_text(self) -> None:
        self.letters_info = []
        letter_contours, grid_img = self._get_letter_contours()

        for l_con in letter_contours:
            letter_img, l_bbox = self._create_letter_square_img(grid_img, l_con, 5)
            preprocessed = self._preprocess_letter_img(letter_img)
            text, _ = self._get_letter_text(preprocessed)

            if text == "l":
                text = "I"

            cx = l_bbox[0] + l_bbox[2] // 2
            cy = l_bbox[1] + l_bbox[3] // 2
            self.letters_info.append((cx, cy, text))

    def _convert_to_letter_grid(self) -> None:
        n = len(self.letters_info)
        root = math.isqrt(n)

        if root * root != n or n < 2:
            self.contour_info_grid = []
            return

        self.letters_info.sort(key=lambda item: item[1])
        self.contour_info_grid = [
            sorted(self.letters_info[i : i + root], key=lambda x: x[0])
            for i in range(0, n, root)
        ]
