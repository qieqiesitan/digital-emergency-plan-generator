"""三个"上传类"端点实测：

1) POST /extraction/parse-file          —— 本地文档解析（**不调 AI**，之前被误列为需真实额度）
2) POST /enterprises/{eid}/floors/{fid}/four-color/analyze —— 本地图像识别（同样**不调 AI**）
3) POST /onboarding/import              —— 真的调 AI（用 mock 供应商零成本覆盖）
"""
import io
import os
import struct
import sys
import zlib

import httpx

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api/v1")
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
FLOOR = os.environ.get("FLOOR_ID", "704841f9-fe85-4cfb-838f-63de6f211149")

PASS, BAD = [], []


def png_with_blocks(path_blocks: list[tuple[tuple[int, int, int, int], tuple[int, int, int]]],
                    width: int = 800, height: int = 600) -> bytes:
    """纯 stdlib 生成 PNG：先铺白底，再按 (x0,y0,x1,y1) 涂色块。"""
    canvas = [[(255, 255, 255)] * width for _ in range(height)]
    for (x0, y0, x1, y1), rgb in path_blocks:
        for y in range(y0, y1):
            row = canvas[y]
            for x in range(x0, x1):
                row[x] = rgb
    raw = b"".join(
        b"\x00" + b"".join(struct.pack("BBB", *px) for px in row) for row in canvas
    )

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def main() -> None:
    with httpx.Client(timeout=120) as c:
        r = c.post(f"{BASE}/auth/login", json={"email": U, "password": P})
        token = (r.json().get("data") or {}).get("access_token")
        h = {"Authorization": f"Bearer {token}"}

        # 1) 文档解析：本地能力，不需要 AI
        csv = "名称,型号,数量\n灭火器,MFZ/ABC4,12\n消防栓,SN65,3\n".encode("utf-8-sig")
        resp = c.post(f"{BASE}/extraction/parse-file", headers=h,
                      files={"file": ("资源清单.csv", csv, "text/csv")})
        ok = resp.status_code == 200 and "灭火器" in resp.text
        (PASS if ok else BAD).append("parse-file")
        print(f"{'✅' if ok else '❌'} POST /extraction/parse-file  {resp.status_code} {resp.text[:90]}")

        # 2) 四色图识别：本地图像处理，不需要 AI
        png = png_with_blocks([
            ((40, 40, 380, 280), (255, 0, 0)),      # 红 → 重大
            ((420, 40, 760, 280), (255, 127, 0)),   # 橙 → 较大
            ((40, 320, 380, 560), (255, 255, 0)),   # 黄 → 一般
            ((420, 320, 760, 560), (0, 0, 255)),    # 蓝 → 低
        ])
        resp = c.post(f"{BASE}/enterprises/{ENT}/risk-management/floors/{FLOOR}/four-color/analyze",
                      headers=h, files={"file": ("四色图.png", png, "image/png")})
        body = resp.text[:160]
        ok = resp.status_code == 200 and '"zones"' in resp.text
        (PASS if ok else BAD).append("four-color/analyze")
        print(f"{'✅' if ok else '❌'} POST /floors/{FLOOR[:8]}/four-color/analyze  {resp.status_code} {body}")
        if resp.status_code == 200:
            data = resp.json().get("data") or {}
            print(f"     识别到分区 {len(data.get('zones') or [])} 个；预览图 token={bool(data.get('token'))}")

        # 3) 组织引导导入：真实调 AI（走 mock）
        resp = c.post(f"{BASE}/onboarding/import", headers=h,
                      data={"module": "resources"},
                      files={"file": ("资源清单.csv", csv, "text/csv")})
        ok = resp.status_code == 200
        (PASS if ok else BAD).append("onboarding/import")
        print(f"{'✅' if ok else '❌'} POST /onboarding/import  {resp.status_code} {resp.text[:110]}")

    print(f"\n==== 上传类端点：PASS {len(PASS)} / 失败 {len(BAD)} {BAD}")
    sys.exit(1 if BAD else 0)


if __name__ == "__main__":
    main()
