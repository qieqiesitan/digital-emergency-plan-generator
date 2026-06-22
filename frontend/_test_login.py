import httpx, asyncio
async def run():
    async with httpx.AsyncClient() as c:
        # Test login API directly
        r = await c.post("http://localhost:8000/api/v1/auth/login", 
            json={"email": "admin@test.com", "password": "admin123"},
            timeout=10)
        print(f"Login API: {r.status_code}")
        print(r.text[:200])
        
        # Test frontend
        r2 = await c.get("http://localhost:5173", timeout=10)
        print(f"\nFrontend: {r2.status_code}")
asyncio.run(run())
