from app.alerts.formatter import append_original_messages_to_summary


def test_append_originals_truncates_long_telegram():
    head = "x" * 100
    sell = "S" * 5000
    buy = "B" * 5000
    out = append_original_messages_to_summary(head, sell, buy)
    assert out.startswith(head)
    assert "Seller (original message)" in out
    assert "Buyer (original message)" in out
    assert len(out) <= 3900
