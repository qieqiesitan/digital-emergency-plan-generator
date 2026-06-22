import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app

async def test():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        print("Login:", resp.status_code)
        token = resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/plans/enterprise-summary", headers=headers)
        print("Summary status:", resp.status_code)
        data = resp.json()
        items = data.get("data", [])
        print("Summary items:", len(items))
        for item in items:
            print(f"  {item['enterprise_name']}: total={item['total']} comp={item['comprehensive_count']} spec={item['special_count']} onsite={item['onsite_count']}")
asyncio.run(test())
