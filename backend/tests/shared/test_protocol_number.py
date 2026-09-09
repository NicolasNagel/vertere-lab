from app.shared.domain.protocol_number import format_protocol_number, present_protocol_number


def test_format_protocol_number_uses_sequence_and_two_digit_year() -> None:
    assert format_protocol_number(year=2026, sequence=1) == "P000001/26"


def test_present_protocol_number_converts_historical_format_only_for_output() -> None:
    assert present_protocol_number("2026/000042") == "P000042/26"


def test_present_protocol_number_preserves_current_and_external_references() -> None:
    assert present_protocol_number("P000042/26") == "P000042/26"
    assert present_protocol_number("LEGACY-42") == "LEGACY-42"
    assert present_protocol_number(None) is None
