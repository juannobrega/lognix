from httpx import AsyncClient

from lognix import __version__


async def test_health_is_public_and_reports_version(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == __version__
    assert body["components"]["postgres"]["ok"] is True
    assert body["status"] == "ok"
    assert {"loki", "alloy"} <= body["components"].keys()
