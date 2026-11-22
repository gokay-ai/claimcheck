from claimcheck.text import split_claims, terms


def test_claims_keep_offsets_into_the_answer() -> None:
    answer = "Memory holds 3 to 5 items.  That replaced 7. It was Miller's figure!"
    claims = split_claims(answer)
    assert [claim.text for claim in claims] == [
        "Memory holds 3 to 5 items.",
        "That replaced 7.",
        "It was Miller's figure!",
    ]
    for claim in claims:
        assert answer[claim.start : claim.end] == claim.text


def test_abbreviations_initials_and_decimals_do_not_split() -> None:
    answer = "G. A. Miller put it at 7.5 items, e.g. digits. Cowan et al. revised it."
    assert [claim.text for claim in split_claims(answer)] == [
        "G. A. Miller put it at 7.5 items, e.g. digits.",
        "Cowan et al. revised it.",
    ]


def test_an_answer_without_a_final_stop_is_one_claim() -> None:
    assert [claim.text for claim in split_claims("No stop at the end")] == ["No stop at the end"]
    assert split_claims("   ") == []


def test_terms_drop_stop_words_and_strip_plurals() -> None:
    assert terms("What are the thresholds of chunking?") == ["threshold", "chunk"]
