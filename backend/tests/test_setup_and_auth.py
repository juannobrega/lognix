from httpx import AsyncClient

from tests.conftest import FIRST_USER


async def test_setup_flow(client: AsyncClient) -> None:
    status = await client.get("/api/v1/setup/status")
    assert status.json() == {"needs_setup": True}

    created = await client.post("/api/v1/setup", json=FIRST_USER)
    assert created.status_code == 201
    body = created.json()
    assert body["user"]["email"] == FIRST_USER["email"]
    assert body["access_token"]
    assert "lognix_refresh" in created.cookies

    status = await client.get("/api/v1/setup/status")
    assert status.json() == {"needs_setup": False}

    again = await client.post("/api/v1/setup", json=FIRST_USER)
    assert again.status_code == 404
    assert again.json()["error"]["code"] == "not_found"


async def test_setup_rejects_short_password(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/setup", json={**FIRST_USER, "password": "curta"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_login_success_and_failure_are_indistinguishable(authed: AsyncClient) -> None:
    ok = await authed.post(
        "/api/v1/auth/login",
        json={"email": FIRST_USER["email"], "password": FIRST_USER["password"]},
    )
    assert ok.status_code == 200

    wrong_pw = await authed.post(
        "/api/v1/auth/login", json={"email": FIRST_USER["email"], "password": "errada-errada"}
    )
    no_user = await authed.post(
        "/api/v1/auth/login", json={"email": "ninguem@x.io", "password": "errada-errada"}
    )
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


async def test_me_requires_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_me_with_token(authed: AsyncClient) -> None:
    resp = await authed.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == FIRST_USER["email"]


async def test_refresh_rotates_and_detects_reuse(client: AsyncClient) -> None:
    first = await client.post("/api/v1/setup", json=FIRST_USER)
    old_cookie = first.cookies["lognix_refresh"]

    refreshed = await client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    new_cookie = refreshed.cookies["lognix_refresh"]
    assert new_cookie != old_cookie

    # Reuso do refresh antigo: toda a família cai.
    client.cookies.set("lognix_refresh", old_cookie, path="/api/v1/auth")
    reused = await client.post("/api/v1/auth/refresh")
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "refresh_reused"

    client.cookies.set("lognix_refresh", new_cookie, path="/api/v1/auth")
    after = await client.post("/api/v1/auth/refresh")
    assert after.status_code == 401


async def test_logout_revokes_refresh(client: AsyncClient) -> None:
    await client.post("/api/v1/setup", json=FIRST_USER)
    out = await client.post("/api/v1/auth/logout")
    assert out.status_code == 204
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


async def test_login_rate_limit(client: AsyncClient) -> None:
    await client.post("/api/v1/setup", json=FIRST_USER)
    bad = {"email": FIRST_USER["email"], "password": "errada-errada"}
    codes = [(await client.post("/api/v1/auth/login", json=bad)).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429
