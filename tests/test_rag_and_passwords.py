from eduassist.rag.ingest import split_markdown
from eduassist.rag.store import keyword_query
from eduassist.security.passwords import hash_password, verify_password


def test_keyword_query_drops_stopwords_and_punctuation():
    assert keyword_query("Có cho trả góp không?") == "trả | góp"


def test_keyword_query_is_safe_for_tsquery_syntax():
    # Ký tự đặc biệt của tsquery (&, |, !, :, ') không được lọt vào câu truy vấn
    q = keyword_query("học phí & ưu đãi | 'drop' !:*")
    assert all(ch not in q.replace(" | ", "") for ch in "&|!:'*")


def test_keyword_query_empty_when_only_stopwords():
    assert keyword_query("có không ạ?") == ""


def test_split_markdown_by_section_with_title():
    md = "# Chính sách\n\nMở đầu bị bỏ qua.\n\n## Hoàn tiền\nHoàn 100%.\n\n## Bảo lưu\nTối đa 6 tháng.\n"
    assert split_markdown(md) == [
        ("Chính sách › Hoàn tiền", "Hoàn 100%."),
        ("Chính sách › Bảo lưu", "Tối đa 6 tháng."),
    ]


def test_split_markdown_splits_long_section_by_paragraph():
    para = "x" * 700
    chunks = split_markdown(f"# T\n## Dài\n{para}\n\n{para}\n\n{para}\n")
    assert len(chunks) == 3
    assert all(section == "T › Dài" for section, _ in chunks)


def test_password_roundtrip():
    stored = hash_password("demo123")
    assert verify_password("demo123", stored)
    assert not verify_password("demo124", stored)
    assert hash_password("demo123") != stored  # salt ngẫu nhiên


def test_verify_password_rejects_garbage():
    assert not verify_password("x", "not-a-hash")
