"""Lab 7 - fuzz testing processor.py with Hypothesis.

SRN: PES2UG24AM091 - Mohammed Muaz Iqubal

Contract under test: given ANY input (random text or None), each function must
either return a result or raise ValueError with a clear message. Any other
exception (AttributeError, KeyError, ZeroDivisionError, OverflowError, ...)
is a crash that Hypothesis has found, so the test fails.
"""
import math

import pytest
from hypothesis import given, settings, strategies as st

from processor import parse_storage_quota, compute_compression_ratio, lookup_bandwidth_tier_rate

FUZZ = settings(max_examples=500, deadline=None)


# ---------- 1. pure fuzzing: random text / None must never crash ----------

@FUZZ
@given(st.text() | st.none())
def test_parse_storage_quota_no_crash(s):
    try:
        result = parse_storage_quota(s)
        assert result.startswith("Quota: ") and result.endswith(" GB")
    except ValueError:
        pass  # invalid input rejected cleanly - expected


@FUZZ
@given(st.text() | st.none())
def test_compute_compression_ratio_safe(s):
    try:
        ratio = compute_compression_ratio(s)
        assert isinstance(ratio, float) and math.isfinite(ratio)
    except ValueError:
        pass


@FUZZ
@given(st.text() | st.none())
def test_lookup_bandwidth_tier_rate_safe(s):
    try:
        rate = lookup_bandwidth_tier_rate(s)
        assert rate in (0.08, 0.05, 0.02)
    except ValueError:
        pass


# ---------- 2. structured fuzzing: input shaped like the real format ----------

@FUZZ
@given(st.integers(min_value=-10**400, max_value=10**400),
       st.sampled_from(["MB", "GB", "TB", "mb", "Tb", "KB", "XB", "B", ""]),
       st.sampled_from(["", " ", "  \t"]))
def test_parse_storage_quota_structured(n, unit, pad):
    try:
        parse_storage_quota(f"{pad}{n}{unit}{pad}")
    except ValueError:
        pass


@FUZZ
@given(st.floats(allow_nan=True, allow_infinity=True) | st.integers(),
       st.floats(allow_nan=True, allow_infinity=True) | st.integers())
def test_compute_compression_ratio_structured(raw, comp):
    try:
        ratio = compute_compression_ratio(f"{raw}:{comp}")
        assert math.isfinite(ratio) and ratio >= 0
    except ValueError:
        pass


@FUZZ
@given(st.sampled_from(["HOT", "COLD", "ARCHIVE", "hot_tier", "Cool", "ARC", "PREMIUM", "HO", ""]),
       st.text(max_size=5))
def test_lookup_bandwidth_tier_rate_structured(prefix, suffix):
    try:
        lookup_bandwidth_tier_rate(prefix + suffix)
    except ValueError:
        pass


# ---------- 3. property checks on valid input (results must be correct) ----------

@given(st.integers(min_value=0, max_value=10**6), st.sampled_from(["MB", "GB", "TB"]))
def test_parse_storage_quota_valid_values(n, unit):
    factor = {"MB": 0.001, "GB": 1.0, "TB": 1000.0}[unit]
    assert parse_storage_quota(f"{n}{unit}") == f"Quota: {n * factor:.2f} GB"


@given(st.integers(min_value=0, max_value=10**9), st.integers(min_value=1, max_value=10**9))
def test_compression_ratio_valid_values(raw, comp):
    assert compute_compression_ratio(f"{raw}:{comp}") == round(raw / comp, 2)


@pytest.mark.parametrize("tier, rate", [("HOT_TIER", 0.08), ("cold", 0.05),
                                         ("  Archive ", 0.02), ("COLDLINE", 0.05)])
def test_known_tiers(tier, rate):
    assert lookup_bandwidth_tier_rate(tier) == rate
