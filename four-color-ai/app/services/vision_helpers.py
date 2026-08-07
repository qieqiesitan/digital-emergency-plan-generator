"""四色图识别视觉辅助：RapidOCR 文字提取（延迟加载 + 降级）。"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

_ocr = None
_clip = None
CLIP_PROMPTS = ["风险分区色块", "图标或Logo", "图例色块", "文字标签"]


def load_ocr():
    """延迟加载 RapidOCR；失败返回 None（调用方降级为空结果）。"""
    global _ocr
    if _ocr is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ocr = RapidOCR()
        except Exception:
            _ocr = False
    return _ocr or None


def extract_texts(bgr_image: np.ndarray) -> list[dict]:
    """对 BGR 图像执行 OCR，返回 [{points: [{x,y}*4], text, confidence}]；模型缺失/异常返回空列表。"""
    engine = load_ocr()
    if engine is None:
        return []
    try:
        result, _ = engine(bgr_image)
    except Exception:
        return []
    texts: list[dict] = []
    for item in result or []:
        box, text, score = item[0], item[1], item[2]
        texts.append({
            "points": [{"x": float(p[0]), "y": float(p[1])} for p in box],
            "text": str(text),
            "confidence": float(score),
        })
    return texts


def _models_dir() -> Path:
    return Path(os.environ.get("FOUR_COLOR_MODELS_DIR", Path(__file__).resolve().parents[2] / "models"))


def load_clip():
    """延迟加载 CLIP 视觉编码器（ONNX）+ 预计算提示词 embedding；资产缺失返回 None。"""
    global _clip
    if _clip is None:
        try:
            import onnxruntime as ort
            vision_path = _models_dir() / "clip_vision.onnx"
            prompts_path = _models_dir() / "clip_prompts.npz"
            if not vision_path.exists() or not prompts_path.exists():
                _clip = False
            else:
                _clip = {
                    "session": ort.InferenceSession(str(vision_path), providers=["CPUExecutionProvider"]),
                    "prompts": np.load(prompts_path),
                }
        except Exception:
            _clip = False
    return _clip or None


def _preprocess_crop(crop_bgr: np.ndarray, size: int = 224) -> np.ndarray:
    import cv2
    img = cv2.resize(crop_bgr, (size, size))
    img = img.astype(np.float32) / 255.0
    mean = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
    std = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
    img = (img - mean) / std
    return img.transpose(2, 0, 1)[None, ...]


def classify_region(crop_bgr: np.ndarray, threshold: float = 0.72) -> str | None:
    """对疑似色块裁剪图做零样本分类：返回"疑似<标签>"；判定为风险分区或置信不足返回 None。"""
    clip = load_clip()
    if clip is None:
        return None
    try:
        x = _preprocess_crop(crop_bgr)
        out = clip["session"].run(None, {"pixel_values": x})[0]
        emb = out[0].astype(np.float32)
        emb = emb / (np.linalg.norm(emb) + 1e-8)
        labels = list(clip["prompts"]["labels"])
        embs = clip["prompts"]["embeddings"].astype(np.float32)
        embs = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8)
        scores = embs @ emb
        best = int(np.argmax(scores))
        if float(scores[best]) < threshold or labels[best] == "风险分区色块":
            return None
        return f"疑似{labels[best]}"
    except Exception:
        return None
