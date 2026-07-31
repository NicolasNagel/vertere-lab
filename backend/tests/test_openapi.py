from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.main import create_app


def _schema() -> dict[str, Any]:
    settings = Settings(
        _env_file=None,
        env="test",
        database_url="postgresql+psycopg://test:test@localhost/test",
    )
    return create_app(settings).openapi()


def test_openapi_declares_cookie_auth_only_on_authenticated_operations() -> None:
    schema = _schema()

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


def test_every_paginated_operation_has_the_uniform_response_contract() -> None:
    schema = _schema()
    components = schema["components"]["schemas"]
    paginated_operations = 0

    for methods in schema["paths"].values():
        for operation in methods.values():
            parameters = {parameter["name"] for parameter in operation.get("parameters", [])}
            if "page_size" not in parameters:
                continue
            paginated_operations += 1
            response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
            component_name = response_schema["$ref"].rsplit("/", 1)[-1]
            properties = components[component_name]["properties"]
            assert {"items", "total", "page", "page_size"} <= properties.keys()

    assert paginated_operations == 10


def test_every_json_mutation_rejects_unknown_fields() -> None:
    schema = _schema()
    checked_schemas: set[str] = set()

    for methods in schema["paths"].values():
        for method, operation in methods.items():
            if method not in {"post", "put", "patch"}:
                continue
            content = operation.get("requestBody", {}).get("content", {})
            request_schema = content.get("application/json", {}).get("schema", {})
            reference = request_schema.get("$ref")
            if reference is None:
                continue
            component_name = reference.rsplit("/", 1)[-1]
            checked_schemas.add(component_name)
            component = schema["components"]["schemas"][component_name]
            assert component.get("additionalProperties") is False, component_name

    assert len(checked_schemas) >= 15
