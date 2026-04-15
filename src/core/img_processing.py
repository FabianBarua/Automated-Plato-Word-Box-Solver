from __future__ import annotations

import logging
import math
import time
from pathlib import Path
from typing import TYPE_CHECKING, List

import cv2
import numpy as np
import win32con
import win32gui
import win32ui
from PIL import Image

from ml.letter_classifier import LetterClassifier

log = logging.getLogger("img_processing")

if TYPE_CHECKING:
    from core.controller import AppController

from core.paths import SCREENSHOT_DIR
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class ImgProcessing:
    def __init__(self, controller: AppController) -> None:
        self.controller = controller
        self.classifier = LetterClassifier()
        self.contour_info_grid: list = []

        self.window_left: int = 0
        self.window_top: int = 0
        self.window_width: int = 0
        self.window_height: int = 0

        self.is_processing: bool = False
        self.img = None
        self.letters_info: List[tuple[int, int, str]] = []

        self.image_path = SCREENSHOT_DIR / "wordbox.png"

    # ── Pipeline ────────────────────────────────────────────────────

    def pipeline(self) -> None:
        app = self.controller.app
        app.is_scanning = True
        self.contour_info_grid = []
        self.letters_info = []
        t0 = time.perf_counter()
        log.info("pipeline() start")

        try:
            self._screenshot_window()
            log.debug("  screenshot saved (%dx%d)", self.window_width, self.window_height)
            self.img = cv2.imread(str(self.image_path))
            if self.img is None:
                log.error("  failed to read screenshot image")
                return
            self._img_to_text()
            self._convert_to_letter_grid()

            log.info("pipeline() done in %.3fs — %d letters detected",
                     time.perf_counter() - t0, len(self.letters_info))
        except Exception:
            log.exception("pipeline() crashed")
        finally:
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
        self.window_width = width
        self.window_height = height

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

        # Cleanup GDI objects
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
        win32gui.DeleteObject(bitmap.GetHandle())

    # ── Grid detection (multi-method: Canny + HoughCircles) ──────────

    @staticmethod
    def _dedup(candidates, threshold=20):
        candidates = sorted(candidates, key=lambda t: (t[1], t[0]))
        result = []
        used = set()
        for i, t in enumerate(candidates):
            if i in used:
                continue
            group = [t]
            for j in range(i + 1, len(candidates)):
                if j in used:
                    continue
                if math.hypot(t[0] - candidates[j][0], t[1] - candidates[j][1]) < threshold:
                    group.append(candidates[j])
                    used.add(j)
            used.add(i)
            result.append((int(np.median([g[0] for g in group])),
                           int(np.median([g[1] for g in group]))))
        return result

    @staticmethod
    def _cluster_1d(vals, tol):
        vals = sorted(vals)
        clusters = []
        for v in vals:
            placed = False
            for i, c in enumerate(clusters):
                if abs(v - c) < tol:
                    clusters[i] = (c + v) // 2
                    placed = True
                    break
            if not placed:
                clusters.append(v)
        return sorted(clusters)

    @staticmethod
    def _fit_grid(centers, h, w):
        if len(centers) < 9:
            return None
        tol = min(h, w) * 0.04
        rows_y = ImgProcessing._cluster_1d([c[1] for c in centers], tol)
        cols_x = ImgProcessing._cluster_1d([c[0] for c in centers], tol)
        if len(rows_y) < 3 or len(cols_x) < 3 or abs(len(rows_y) - len(cols_x)) > 1:
            return None
        n = max(len(rows_y), len(cols_x))
        rs = [rows_y[i + 1] - rows_y[i] for i in range(len(rows_y) - 1)]
        cs = [cols_x[i + 1] - cols_x[i] for i in range(len(cols_x) - 1)]
        row_var = (max(rs) - min(rs)) / np.mean(rs) if len(rs) > 1 else 0
        col_var = (max(cs) - min(cs)) / np.mean(cs) if len(cs) > 1 else 0
        hits = 0
        for ry in rows_y:
            for cx in cols_x:
                for c in centers:
                    if abs(c[0] - cx) < tol and abs(c[1] - ry) < tol:
                        hits += 1
                        break
        coverage = hits / (n * n)
        score = coverage - 0.3 * (row_var + col_var)
        return {
            "n": n, "rows": rows_y[:n], "cols": cols_x[:n],
            "score": score,
            "step_x": int(np.median(cs)), "step_y": int(np.median(rs)),
        }

    @staticmethod
    def _canny_candidates(gray, img_area):
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        raw = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < img_area * 0.003 or area > img_area * 0.08:
                continue
            x2, y2, w2, h2 = cv2.boundingRect(c)
            asp = w2 / h2 if h2 else 0
            if 0.7 < asp < 1.4:
                raw.append((x2 + w2 // 2, y2 + h2 // 2, area))
        if not raw:
            return []
        areas = sorted([t[2] for t in raw])
        med = areas[len(areas) // 2]
        return ImgProcessing._dedup(
            [(t[0], t[1]) for t in raw if 0.5 < t[2] / med < 2.0], 20
        )

    @staticmethod
    def _hough_candidates(gray, w, h):
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        circles = cv2.HoughCircles(
            blurred, cv2.HOUGH_GRADIENT, 1.2,
            minDist=int(min(w, h) * 0.08),
            param1=100, param2=30,
            minRadius=int(min(w, h) * 0.04),
            maxRadius=int(min(w, h) * 0.13),
        )
        if circles is None:
            return []
        radii = sorted([int(c[2]) for c in circles[0]])
        q1, q3 = radii[len(radii) // 4], radii[3 * len(radii) // 4]
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * max(iqr, 3), q3 + 1.5 * max(iqr, 3)
        return ImgProcessing._dedup(
            [(int(c[0]), int(c[1])) for c in circles[0] if lo <= int(c[2]) <= hi], 25
        )

    def _detect_grid(self):
        h, w = self.img.shape[:2]
        gray = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)
        img_area = h * w

        canny_pts = self._canny_candidates(gray, img_area)
        hough_pts = self._hough_candidates(gray, w, h)

        best = None
        for pts in [canny_pts, hough_pts, self._dedup(canny_pts + hough_pts, 25)]:
            result = self._fit_grid(pts, h, w)
            if result and (best is None or result["score"] > best["score"]):
                best = result

        if best is None:
            log.warning("  grid detection FAILED (no candidates)")
            return None

        n = best["n"]
        tile_size = int(min(best["step_x"], best["step_y"]) * 0.55)
        log.info("  grid detected: %dx%d, tile_size=%d, score=%.3f",
                 n, n, tile_size, best["score"])

        grid = []
        for ry in best["rows"]:
            row = [(cx, ry, tile_size) for cx in best["cols"]]
            grid.append(row)
        return grid, n, tile_size

    # ── Letter extraction ───────────────────────────────────────────

    @staticmethod
    def _make_clean_letter(contour, thresh_img):
        x, y, w, h = cv2.boundingRect(contour)
        mask_crop = thresh_img[y:y + h, x:x + w]
        clean = cv2.bitwise_not(mask_crop)
        clean_rgb = cv2.cvtColor(clean, cv2.COLOR_GRAY2RGB)
        size = max(w, h) + 10
        padded = np.ones((size, size, 3), dtype=np.uint8) * 255
        xo, yo = (size - w) // 2, (size - h) // 2
        padded[yo:yo + h, xo:xo + w] = clean_rgb
        return padded

    @staticmethod
    def _fix_char(char):
        if char == "l":
            return "I"
        if len(char) == 1:
            return char.upper()
        return char

    def _extract_letter_from_tile(self, cx, cy, tile_size):
        h_img, w_img = self.img.shape[:2]
        half = tile_size // 2
        y1, y2 = max(0, cy - half), min(h_img, cy + half)
        x1, x2 = max(0, cx - half), min(w_img, cx + half)

        tile = self.img[y1:y2, x1:x2]
        if tile.size == 0:
            return None

        gray = cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        tile_area = tile.shape[0] * tile.shape[1]
        sig = [c for c in contours if cv2.contourArea(c) > tile_area * 0.02]
        if not sig:
            return None

        if len(sig) > 1:
            sig.sort(key=lambda c: cv2.boundingRect(c)[0])
            text, total_conf = "", 0.0
            for cont in sig:
                padded = self._make_clean_letter(cont, thresh)
                char, conf = self.classifier.read_letter(padded)
                text += char
                total_conf += conf
            return self._fix_char(text), total_conf / len(sig)

        padded = self._make_clean_letter(np.vstack(sig), thresh)
        char, conf = self.classifier.read_letter(padded)
        return self._fix_char(char), conf

    # ── Tile image extraction (batch) ───────────────────────────────

    def _extract_letter_images_from_tile(self, cx, cy, tile_size):
        """Extract clean letter image(s) from a tile without classifying."""
        h_img, w_img = self.img.shape[:2]
        half = tile_size // 2
        y1, y2 = max(0, cy - half), min(h_img, cy + half)
        x1, x2 = max(0, cx - half), min(w_img, cx + half)

        tile = self.img[y1:y2, x1:x2]
        if tile.size == 0:
            return []

        gray = cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return []

        tile_area = tile.shape[0] * tile.shape[1]
        sig = [c for c in contours if cv2.contourArea(c) > tile_area * 0.02]
        if not sig:
            return []

        if len(sig) > 1:
            sig.sort(key=lambda c: cv2.boundingRect(c)[0])
            return [self._make_clean_letter(cont, thresh) for cont in sig]

        return [self._make_clean_letter(np.vstack(sig), thresh)]

    # ── OCR (batch) ─────────────────────────────────────────────────

    def _img_to_text(self) -> None:
        self.letters_info = []
        result = self._detect_grid()
        if not result:
            return

        grid, n, tile_size = result

        # Phase 1: Extract all letter images
        tile_data = []
        all_images = []

        for row in grid:
            for cx, cy, ts in row:
                images = self._extract_letter_images_from_tile(cx, cy, ts)
                tile_data.append((cx, cy, len(images)))
                all_images.extend(images)

        # Phase 2: Batch classify all images at once
        t_ocr = time.perf_counter()
        if all_images:
            results = self.classifier.read_letters_batch(all_images)
        else:
            results = []
        log.debug("  batch OCR: %d images in %.3fs",
                  len(all_images), time.perf_counter() - t_ocr)

        # Phase 3: Reconstruct text for each tile
        idx = 0
        for cx, cy, count in tile_data:
            if count == 0:
                self.letters_info.append((cx, cy, "?"))
            else:
                text = ""
                for _ in range(count):
                    char, _ = results[idx]
                    text += char
                    idx += 1
                self.letters_info.append((cx, cy, self._fix_char(text)))

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
