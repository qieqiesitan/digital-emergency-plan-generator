import httpx

r = httpx.post("http://localhost:8000/api/v1/auth/login", json={"email": "qa_e2e_test@test.com", "password": "test123456"}, timeout=10)
token = r.json()["data"]["access_token"]
print("Logged in")

r2 = httpx.get("http://localhost:8000/api/v1/enterprises", headers={"Authorization": f"Bearer {token}"}, timeout=10)
ents = r2.json()["data"]["items"]
eid = ents[0]["id"]
print("Using enterprise:", ents[0]["name"])

r3 = httpx.post("http://localhost:8000/api/v1/plans", json={
    "enterprise_id": eid, "plan_type": "comprehensive",
    "title": "Test_CM_" + str(hash(str(ents)))[:6],
}, headers={"Authorization": f"Bearer {token}"}, timeout=10)
plan = r3.json()["data"]
print("Plan:", plan["title"], "sections:", plan["sections_count"])

r4 = httpx.get(f"http://localhost:8000/api/v1/plans/{plan['id']}/sections", headers={"Authorization": f"Bearer {token}"}, timeout=10)
sections = r4.json()["data"]
print("Actual sections:", len(sections))
for s in sections[:5]:
    print(" ", s["section_key"], ":", s["title"])
if len(sections) > 5:
    print("  ... and", len(sections)-5, "more")
