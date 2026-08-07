"""四色图识别视觉辅助：RapidOCR 文字提取（延迟加载 + 降级）。"""
from __future__ import annotations

import numpy as np

_ocr = None


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
