"""企业信息自动填充预研 — 多轮搜索 + 字段提取 + 交叉验证"""
import re, time
from scrapling import Fetcher

# 字段提取正则
PATTERNS = {
    "credit_code": r'(?:统一社会信用代码|信用代码)[：:\s]*([0-9A-HJ-NPQRTUWXY]{18})',
    "legal_representative": r'(?:法定代表人|法人)[：:\s]*([\u4e00-\u9fa5]{2,4})',
    "registered_capital": r'(?:注册资本)[：:\s]*([\d,.]+)\s*万?\s*(?:元|人民币|美元)?',
    "established_date": r'(?:成立日期|成立时间)[：:\s]*(\d{4}[年/-]\d{1,2}[月/-]\d{1,2})',
    "address": r'(?:注册地址|公司地址|地址)[：:\s]*([\u4e00-\u9fa5]{6,}(?:省|市|区|县|镇|路|街|号|厦|楼|层|座)[\u4e00-\u9fa5\d\-号楼层]*)',
    "business_scope": r'(?:经营范围)[：:\s]*([\u4e00-\u9fa5、，,，；;]{10,})',
    "economic_type": r'(?:经济类型|企业类型|公司类型)[：:\s]*([\u4e00-\u9fa5]{2,6}(?:企业|公司|独资|合伙|有限))',
    "phone": r'(?:电话|联系电话|电话：)[：:\s]*(\d{3,4}[-]?\d{7,8}|1[3-9]\d{9})',
}

ROUNDS = [
    ("统一社会信用代码 工商信息", ["credit_code"]),
    ("法定代表人 注册资本 成立日期 工商信息", ["legal_representative", "registered_capital", "established_date"]),
    ("注册地址 经营范围 企业类型 工商信息", ["address", "business_scope", "economic_type"]),
    ("企业简介 主营产品 所属行业", ["industry", "main_products"]),
]

def search_and_extract(company: str, search_suffix: str, target_fields: list):
    query = f"{company} {search_suffix}"
    d = Fetcher.get(f"https://cn.bing.com/search?q={query}&count=8")
    results = {}
    sources = set()

    for item in d.css("li.b_algo"):
        title_el = item.css("h2 a")
        snip_el = item.css(".b_caption p")
        if not title_el:
            continue
        url = (title_el[0].attrib or {}).get("href", "")
        if "bing.com" in url:
            continue

        # 识别来源域名
        for domain, label in [("qichacha", "企查查"), ("tianyancha", "天眼查"),
                               ("qixin", "启信宝"), ("baidu.com/item", "百度百科"),
                               ("wikipedia", "维基")]:
            if domain in url:
                sources.add(label)

        text = (title_el[0].text or "") + " " + ((snip_el[0].text or "") if snip_el else "")
        for field in target_fields:
            if field in results:
                continue
            pat = PATTERNS.get(field)
            if not pat:
                continue
            m = re.search(pat, text)
            if m:
                results[field] = (m.group(1).strip(), list(sources)[:3] if sources else ["搜索结果"])

    return results

def autofill_enterprise(company: str):
    all_hits = {}
    print(f"\n{'='*60}")
    print(f"  企业: {company}")
    print(f"{'='*60}")

    for i, (suffix, target_fields) in enumerate(ROUNDS):
        print(f"\n  第{i+1}轮: \"{suffix}\"")
        hits = search_and_extract(company, suffix, target_fields)
        print(f"    命中: {list(hits.keys())}")
        for field, (value, sources) in hits.items():
            if field not in all_hits:
                all_hits[field] = []
            all_hits[field].append((value, sources))
        time.sleep(0.5)

    # 交叉验证
    print(f"\n{'─'*60}")
    print(f"  交叉验证结果")
    print(f"{'─'*60}")

    final = {}
    for field, hit_list in all_hits.items():
        values = [v for v, _ in hit_list]
        all_sources = []
        for _, srcs in hit_list:
            all_sources.extend(srcs)
        all_sources = list(set(all_sources))[:4]

        if len(hit_list) >= 2 and len(set(values)) == 1:
            conf = "high"
            icon = "🟢"
        elif len(values) >= 1:
            conf = "medium"
            icon = "🟡"
        else:
            conf = "low"
            icon = "🔴"

        final[field] = {"value": values[0], "confidence": conf, "sources": all_sources}
        print(f"  {icon} {field}: {values[0][:40]} | {conf} | 来源: {', '.join(all_sources[:3]) or '搜索结果'}")

    print(f"\n  总结: {len(final)} 项信息, "
          f"高置信 {sum(1 for f in final.values() if f['confidence']=='high')}, "
          f"中置信 {sum(1 for f in final.values() if f['confidence']=='medium')}")
    return final


if __name__ == "__main__":
    companies = [
        "华为技术有限公司",
        "比亚迪股份有限公司",
        "中国石油天然气集团有限公司",
        "北京字节跳动科技有限公司",
    ]
    for c in companies:
        try:
            autofill_enterprise(c)
            time.sleep(2)
        except Exception as e:
            print(f"  错误: {e}")
