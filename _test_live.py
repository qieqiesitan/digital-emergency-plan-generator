import requests, json

BASE = "http://localhost:8000/api/v1"
s = requests.Session()

# Step 1: Login
print("1. Login...")
r = s.post(f"{BASE}/auth/login", json={"email": "test@test.com", "password": "test123456"})
if r.status_code != 200:
    print(f"   FAIL: {r.status_code} {r.text[:200]}")
    exit(1)
token = r.json()["data"]["access_token"]
s.headers["Authorization"] = f"Bearer {token}"
print("   OK")

# Step 2: AI config
print("2. AI config...")
r = s.put(f"{BASE}/settings/ai-config", json={
    "provider": "deepseek", "api_key": "sk-e7c71b171d784d0fa18d2c7a8eeb4e09",
    "model_name": "deepseek-v4-flash", "base_url": "https://api.deepseek.com/v1",
    "temperature": 0.3, "max_tokens": 4096, "top_p": 0.95
})
print(f"   {r.status_code}")

# Step 3: Find/Create enterprise
print("3. Enterprise...")
r = s.get(f"{BASE}/enterprises")
items = r.json()["data"]["items"]
if items:
    ent_id = items[0]["id"]
    print(f"   Using: {items[0]['name']}")
else:
    r = s.post(f"{BASE}/enterprises", json={
        "name": "西安宝岳空间科技有限公司", "address": "西安市高新区科技路48号创业广场B座15层",
        "industry": "信息技术服务业", "employee_count": 85,
        "building_overview": "创业广场B座15层整层约1200平方米",
        "org_structure": "总经理-副总经理-各部门",
        "legal_representative": "张三", "phone": "029-88888888", "safety_officer": "李四"
    })
    ent_id = r.json()["data"]["id"]
    print(f"   Created: {ent_id}")

# Step 4: Create plan
print("4. Plan...")
r = s.post(f"{BASE}/plans", json={
    "enterprise_id": ent_id, "plan_type": "comprehensive",
    "title": "测试-综合应急预案(新Prompt)", "accident_type": "综合"
})
plan_id = r.json()["data"]["id"]
print(f"   {plan_id}")

# Step 5: Get sections & find org section
r = s.get(f"{BASE}/plans/{plan_id}/sections")
sections = r.json()["data"]
org_s = next((sec for sec in sections if "组织" in sec.get("title","") or "机构" in sec.get("title","")), sections[3])
sk = org_s["section_key"]
print(f"5. Generate [{sk}] {org_s['title']}...")

# Step 6: SSE stream generation
r = s.post(f"{BASE}/plans/{plan_id}/generate/{sk}", stream=True, timeout=180)
full = ""
for line in r.iter_lines(decode_unicode=True):
    if line and line.startswith("data: "):
        d = json.loads(line[6:])
        t = d.get("type", "")
        if t == "chunk":
            full += d.get("content", "")
        elif t == "progress":
            print(f"   {d.get('message','')}")
        elif t == "done":
            print(f"   DONE ({len(full)} chars)")
        elif t == "error":
            print(f"   ERROR: {d.get('message','')}")

# Step 7: Show & save
print(f"\n{'='*60}")
print(full[:800])
print(f"{'='*60}")

out = r"C:\Users\55061\Documents\数字化预案自动生成 2\prompt_test_results\live_test_output.md"
with open(out, "w", encoding="utf-8") as f:
    f.write(full)
print(f"\nSaved: {out}")
