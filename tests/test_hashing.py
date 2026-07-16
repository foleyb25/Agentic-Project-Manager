from apm.hashing import fingerprint, normalize_summary, sha256_text


def test_normalize_summary_collapses_noise():
    assert normalize_summary("Arc TOO high!!  speed, too slow…") == "arc-too-high-speed-too-slow"


def test_fingerprint_stable_across_role_order_and_case():
    fp1, key1 = fingerprint("tuning", ["gd", "ge"], "passing.lob", "arc too high, speed too slow")
    fp2, key2 = fingerprint("Tuning", ["GE", "gd"], "PASSING.LOB", "Arc too high — speed too slow!")
    assert fp1 == fp2
    assert key1 == key2 == "tuning|gd,ge|passing.lob|arc-too-high-speed-too-slow"


def test_fingerprint_differs_by_feature_area():
    fp1, _ = fingerprint("tuning", ["gd"], "passing.lob", "too slow")
    fp2, _ = fingerprint("tuning", ["gd"], "passing.bullet", "too slow")
    assert fp1 != fp2


def test_sha256_text_matches_known_vector():
    assert sha256_text("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
