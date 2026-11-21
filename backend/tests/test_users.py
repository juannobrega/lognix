from httpx import AsyncClient

from tests.conftest import FIRST_USER

SECOND = {"email": "dev@example.com", "name": "Dev", "password": "outra-senha-456"}


async def test_users_crud(authed: AsyncClient) -> None:
    created = await authed.post("/api/v1/users", json=SECOND)
    assert created.status_code == 201

    dup = await authed.post("/api/v1/users", json=SECOND)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "email_taken"

    listed = await authed.get("/api/v1/users")
    emails = {u["email"] for u in listed.json()}
    assert emails == {FIRST_USER["email"], SECOND["email"]}

    deleted = await authed.delete(f"/api/v1/users/{created.json()['id']}")
    assert deleted.status_code == 204


async def test_cannot_delete_last_user(authed: AsyncClient) -> None:
    me = (await authed.get("/api/v1/auth/me")).json()
    resp = await authed.delete(f"/api/v1/users/{me['id']}")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "last_user"


async def test_change_password(authed: AsyncClient) -> None:
    wrong = await authed.put(
        "/api/v1/users/me/password",
        json={"current_password": "nao-e-essa-1", "new_password": "nova-senha-789"},
    )
    assert wrong.status_code == 400

    ok = await authed.put(
        "/api/v1/users/me/password",
        json={"current_password": FIRST_USER["password"], "new_password": "nova-senha-789"},
    )
    assert ok.status_code == 204

    login = await authed.post(
        "/api/v1/auth/login", json={"email": FIRST_USER["email"], "password": "nova-senha-789"}
    )
    assert login.status_code == 200
