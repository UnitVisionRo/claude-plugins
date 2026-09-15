import httpx

# asyncio_mode = "auto" in pyproject.toml -- no marker needed for pytest-asyncio.


async def test_health() -> None:
    from main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
