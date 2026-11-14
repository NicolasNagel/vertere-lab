import logging

from app.core.logging import StripQueryFromAccessLog


def _access_record(full_path: str) -> logging.LogRecord:
    # Formato real do uvicorn.access: '%s - "%s %s HTTP/%s" %d'
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:5000", "GET", full_path, "1.1", 200),
        None,
    )


def test_access_log_keeps_the_path_and_drops_the_query_with_personal_data() -> None:
    log_filter = StripQueryFromAccessLog()
    with_query = _access_record("/api/v1/clinics?search=78.977.352%2F0001-99&page=1")
    without_query = _access_record("/api/v1/health")

    assert log_filter.filter(with_query) is True
    assert log_filter.filter(without_query) is True

    assert with_query.getMessage() == '127.0.0.1:5000 - "GET /api/v1/clinics HTTP/1.1" 200'
    assert "78.977" not in with_query.getMessage()
    assert without_query.getMessage() == '127.0.0.1:5000 - "GET /api/v1/health HTTP/1.1" 200'
