"""构建期脚本：生成 CLIP 视觉编码器 ONNX 与提示词 embedding。

用法：backend/.venv/Scripts/python.exe scripts/prepare_clip_assets.py
成功：backend/models/clip_vision.onnx + clip_prompts.npz。
失败：打印原因并退出 0（运行期自动降级为纯规则，不阻塞）。
"""
import sys
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parents[1] / "backend" / "models"
PROMPTS = ["风险分区色块", "图标或Logo", "图例色块", "文字标签"]
MODEL_ID = "openai/clip-vit-base-patch32"


def main() -> int:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        import numpy as np
        import torch
        from transformers import CLIPModel, CLIPProcessor, CLIPVisionModel

        model = CLIPModel.from_pretrained(MODEL_ID)
        inputs = CLIPProcessor.from_pretrained(MODEL_ID)(text=PROMPTS, return_tensors="pt")
        with torch.no_grad():
            text_embs = model.get_text_features(**inputs).numpy()
        np.savez(MODELS_DIR / "clip_prompts.npz", labels=np.array(PROMPTS), embeddings=text_embs)

        vision = CLIPVisionModel.from_pretrained(MODEL_ID)
        vision.eval()
        dummy = torch.randn(1, 3, 224, 224)
        torch.onnx.export(
            vision,
            dummy,
            str(MODELS_DIR / "clip_vision.onnx"),
            input_names=["pixel_values"],
            output_names=["image_embeds"],
            opset_version=17,
        )
        print(f"CLIP assets ready: {MODELS_DIR / 'clip_vision.onnx'}, {MODELS_DIR / 'clip_prompts.npz'}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[prepare_clip_assets] 资产准备失败（运行期将降级为纯规则）：{exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
