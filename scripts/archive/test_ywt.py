import asyncio, httpx, json

async def test():
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post('http://ywt-gateway:8080/auth/login',
            json={'username':'admin','password':'admin123'},
            headers={'Content-Type':'application/json','X-Api-Key':'893e5e15d3b444dbbebb1dac44b720f2'})
        j = r.json()
        tk = j['data']['accessToken']
        
        r2 = await c.get('http://ywt-gateway:8080/ai/prompt/list',
            headers={'Authorization': 'Bearer ' + tk})
        d = r2.json()
        print(json.dumps(d, ensure_ascii=False, indent=2)[:2000])

asyncio.run(test())
