"""Pruebas de integración del flujo de autenticación."""

from app.models.user import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import DEFAULT_PASSWORD


async def _login(
    client: AsyncClient,
    *,
    organization_slug: str = "acme",
    email: str = "admin@acme.com",
    password: str = DEFAULT_PASSWORD,
):
    return await client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": organization_slug,
            "email": email,
            "password": password,
        },
    )


async def test_login_returns_token_pair_and_me(client: AsyncClient, admin_a: User) -> None:
    response = await _login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert body["access_token"]
    assert body["refresh_token"]

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == admin_a.email
    assert me.json()["organization_id"] == str(admin_a.organization_id)


async def test_login_with_wrong_password_is_generic(client: AsyncClient, admin_a: User) -> None:
    response = await _login(client, password="Wrong-Password-123")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    body = response.json()
    assert body["status"] == 401
    assert body["detail"] == "Credenciales inválidas."


async def test_login_with_unknown_organization_is_generic(
    client: AsyncClient, admin_a: User
) -> None:
    response = await _login(client, organization_slug="unknown")

    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas."


async def test_inactive_user_cannot_login(
    client: AsyncClient, db_session: AsyncSession, admin_a: User
) -> None:
    admin_a.is_active = False
    await db_session.commit()

    response = await _login(client)

    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas."


async def test_refresh_rotates_tokens(client: AsyncClient, admin_a: User) -> None:
    login = await _login(client)
    first = login.json()

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )

    assert refreshed.status_code == 200
    second = refreshed.json()
    assert second["refresh_token"] != first["refresh_token"]

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {second['access_token']}"},
    )
    assert me.status_code == 200


async def test_reusing_revoked_refresh_token_invalidates_session(
    client: AsyncClient, admin_a: User
) -> None:
    login = await _login(client)
    first = login.json()

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    second = refreshed.json()

    reuse = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert reuse.status_code == 401

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {second['access_token']}"},
    )
    assert me.status_code == 401

    rotated_again = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}
    )
    assert rotated_again.status_code == 401


async def test_logout_is_idempotent(client: AsyncClient, admin_a: User) -> None:
    login = await _login(client)
    tokens = login.json()

    first = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    second = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )

    assert first.status_code == 204
    assert second.status_code == 204

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 401


async def test_missing_and_invalid_access_tokens_are_rejected(
    client: AsyncClient, admin_a: User
) -> None:
    missing = await client.get("/api/v1/auth/me")
    assert missing.status_code == 401
    assert missing.json()["detail"] == "Token de acceso ausente."

    invalid = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert invalid.status_code == 401


async def test_validation_errors_use_problem_details(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"organization_slug": "acme", "email": "not-an-email"}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["type"].endswith("/validation")
    assert body["status"] == 422
    assert body["errors"]


async def test_health_check(client: AsyncClient) -> None:
    for path in ("/health", "/api/v1/health"):
        response = await client.get(path)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] == "ok"


async def test_request_id_is_echoed(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "test-request-id"})

    assert response.headers["X-Request-ID"] == "test-request-id"
