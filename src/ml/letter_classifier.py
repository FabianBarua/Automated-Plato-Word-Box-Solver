import json

import numpy as np
import onnxruntime as ort
from PIL import Image

from core.paths import ML_DIR

# ImageNet normalization constants
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)


class LetterClassifier:
    def __init__(self, device=None):
        model_path = str(ML_DIR / "letter_classifier.onnx")
        self.IMAGE_RESIZE = 32

        with open(ML_DIR / "class_names.json", encoding="utf-8") as f:
            self.class_names = json.load(f)

        providers = ['DmlExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']
        available = ort.get_available_providers()
        selected = [p for p in providers if p in available] or ['CPUExecutionProvider']

        self.session = ort.InferenceSession(
            model_path, providers=selected
        )
        self.input_name = self.session.get_inputs()[0].name

    def _preprocess(self, img: Image.Image) -> np.ndarray:
        img = img.convert("RGB").resize(
            (self.IMAGE_RESIZE, self.IMAGE_RESIZE), Image.BILINEAR
        )
        arr = np.asarray(img, dtype=np.float32) / 255.0  # (H, W, 3)
        arr = arr.transpose(2, 0, 1)                      # (3, H, W)
        arr = (arr - _MEAN) / _STD
        return arr[np.newaxis]                             # (1, 3, H, W)

    def read_letter(self, letter_img):
        if isinstance(letter_img, np.ndarray):
            letter_img = Image.fromarray(letter_img)

        x = self._preprocess(letter_img)
        (logits,) = self.session.run(None, {self.input_name: x})

        # softmax
        exp = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs = exp / exp.sum(axis=1, keepdims=True)

        idx = int(probs.argmax(axis=1)[0])
        confidence = float(probs[0, idx])
        return self.class_names[idx], confidence

    def read_letters_batch(self, images):
        """Classify multiple letter images in a single ONNX inference call."""
        if not images:
            return []

        pil_images = [
            Image.fromarray(img) if isinstance(img, np.ndarray) else img
            for img in images
        ]
        batch = np.concatenate(
            [self._preprocess(img) for img in pil_images], axis=0
        )

        try:
            (logits,) = self.session.run(None, {self.input_name: batch})
        except Exception:
            return [self.read_letter(img) for img in images]

        exp = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs = exp / exp.sum(axis=1, keepdims=True)
        indices = probs.argmax(axis=1)
        return [
            (self.class_names[int(idx)], float(probs[i, idx]))
            for i, idx in enumerate(indices)
        ]
