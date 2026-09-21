"""真实额度 ③⑤⑥：隐患 AI 建议 / 资料导入抽取 / 平面图 AI 分析。"""
import json
import os
import sys
import time

import httpx

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api/v1")
ENT = "10e11995-e682-405a-9035-fbde13cca213"
U, P = "qa_e2e_test@test.com", "test123456"


def show(title: str, status: int, el: float, payload) -> None:
    print(f"\n【{title}】HTTP {status}  {el:.1f}s")
    text = json.dumps(payload, ensure_ascii=False)
    print(text[:900])


def main() -> int:
    with httpx.Client(timeout=300) as c:
        token = (c.post(f"{BASE}/auth/login", json={"email": U, "password": P}).json()
                 .get("data") or {}).get("access_token")
        h = {"Authorization": f"Bearer {token}"}

        # ③-1 隐患描述 → 辅助录入
        t0 = time.perf_counter()
        r = c.post(f"{BASE}/enterprises/{ENT}/hazard-inspection/ai/record-assist", headers=h,
                   json={"description": "巡检发现甲醇储罐区 2# 罐出口管线法兰处有渗漏，地面有少量积液，气味明显。"})
        show("③-1 隐患 AI 辅助录入", r.status_code, time.perf_counter() - t0,
             r.json().get("data") if r.status_code == 200 else r.text[:300])

        # ③-2 行业 + 风险点 → 检查表模板
        t0 = time.perf_counter()
        r = c.post(f"{BASE}/enterprises/{ENT}/hazard-inspection/ai/checklist-template", headers=h,
                   json={"industry": "化工 / 甲醇仓储", "risk_points": "储罐区泄漏、装卸区静电、危废暂存间混放"})
        show("③-2 检查表模板建议", r.status_code, time.perf_counter() - t0,
             r.json().get("data") if r.status_code == 200 else r.text[:300])

        # ⑤ 资料导入抽取（真实 CSV）
        csv = ("队伍名称,队伍类型,人数,负责人,联系电话,主要装备\n"
               "厂区应急抢险队,兼职救援队,18,张伟,13800000001,防爆工具、堵漏套件、正压呼吸器\n"
               "医疗救护组,医疗救护,6,李娜,13800000002,急救箱、担架、氧气瓶\n").encode("utf-8-sig")
        t0 = time.perf_counter()
        r = c.post(f"{BASE}/onboarding/import", headers=h, data={"module": "resources"},
                   files={"file": ("应急资源台账.csv", csv, "text/csv")})
        show("⑤ 资料导入抽取（resources）", r.status_code, time.perf_counter() - t0,
             r.json().get("data") if r.status_code == 200 else r.text[:300])

        # ⑥ 平面图 AI 分析（文本推理，非视觉）
        t0 = time.perf_counter()
        r = c.post(f"{BASE}/enterprises/{ENT}/risk-management/ai/analyze-floor-plan", headers=h,
                   json={"enterprise_info": {
                       "name": "QA 化工仓储", "industry": "危险化学品仓储",
                       "building_overview": "厂区占地 40 亩：西侧甲醇储罐区（4×5000m³ 常压罐、围堰、氮封）、"
                                            "南侧汽车装卸区（3 个鹤管位）、北侧生产辅助楼、东侧危废暂存间。",
                       "hazardous_chemicals": "甲醇 12000t"}})
        show("⑥ 平面图 AI 分析（分区建议）", r.status_code, time.perf_counter() - t0,
             r.json().get("data") if r.status_code == 200 else r.text[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
