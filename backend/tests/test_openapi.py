from __future__ import annotations

from app.main import create_app


def test_openapi_declares_cookie_auth_only_on_authenticated_operations() -> None:
    schema = create_app().openapi()

    cookie_scheme = schema["components"]["securitySchemes"]["SessionCookie"]
    assert cookie_scheme == {
        "type": "apiKey",
        "in": "cookie",
        "name": "vertere_session",
    }
    assert "security" not in schema["paths"]["/api/v1/health"]["get"]
    assert "security" not in schema["paths"]["/api/v1/auth/login"]["post"]
    assert schema["paths"]["/api/v1/auth/me"]["get"]["security"] == [{"SessionCookie": []}]
    assert schema["paths"]["/api/v1/clinics"]["get"]["security"] == [{"SessionCookie": []}]
