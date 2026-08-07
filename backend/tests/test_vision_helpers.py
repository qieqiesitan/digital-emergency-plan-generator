"""vision_helpers 单测：OCR/CLIP 降级与 mock 推理。"""
import numpy as np

import app.services.vision_helpers as vh


def test_extract_texts_degrades_without_model(monkeypatch):
    monkeypatch.setattr(vh, "_ocr", False)
    assert vh.extract_texts(np.zeros((100, 100, 3), dtype=np.uint8)) == []


def test_extract_texts_parses_ocr_output(monkeypatch):
    class FakeEngine:
        def __call__(self, img):
            return ([[[[10, 20], [90, 20], [90, 40], [10, 40]], "ZONE", 0.98]], None)

    monkeypatch.setattr(vh, "_ocr", FakeEngine())
    texts = vh.extract_texts(np.zeros((200, 200, 3), dtype=np.uint8))
    assert texts[0]["text"] == "ZONE"
    assert texts[0]["confidence"] == 0.98
    assert len(texts[0]["points"]) == 4


def test_extract_texts_returns_empty_on_engine_error(monkeypatch):
    class BrokenEngine:
        def __call__(self, img):
            raise RuntimeError("boom")

    monkeypatch.setattr(vh, "_ocr", BrokenEngine())
    assert vh.extract_texts(np.zeros((100, 100, 3), dtype=np.uint8)) == []
