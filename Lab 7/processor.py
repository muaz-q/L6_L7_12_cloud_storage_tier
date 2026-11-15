import math
import re

# Fixes found by fuzzing (Lab 7): every invalid input now raises ValueError
# with a clear message instead of crashing with AttributeError, KeyError,
# OverflowError or ZeroDivisionError.

_QUOTA_PATTERN = re.compile(r"(\d+)(MB|GB|TB)", re.ASCII)


def parse_storage_quota(quota_str):
    """
    Parses storage quota string with unit suffix into Gigabytes (GB).
    Assumes format: '<digits><2-letter unit>' (e.g. '500MB', '20GB', '2TB').
    Raises ValueError for anything else.
    """
    if not isinstance(quota_str, str):
        raise ValueError("Quota must be a string like '500MB'")
    cleaned = quota_str.strip().upper()
    match = _QUOTA_PATTERN.fullmatch(cleaned)
    if match is None:
        raise ValueError(f"Invalid quota {quota_str!r}: expected digits followed by MB, GB or TB")
    val_str, unit = match.groups()
    value = int(val_str)  # very long digit strings raise ValueError here
    multipliers = {
        "MB": 0.001,
        "GB": 1.0,
        "TB": 1000.0
    }
    try:
        gb_total = value * multipliers[unit]
    except OverflowError:
        raise ValueError("Quota value is too large") from None
    return f"Quota: {gb_total:.2f} GB"

def compute_compression_ratio(size_metric_str):
    """
    Computes compression ratio: raw_bytes / compressed_bytes.
    Assumes format: 'raw_bytes:compressed_bytes' (e.g. '1024:256').
    Raises ValueError for anything else.
    """
    if not isinstance(size_metric_str, str):
        raise ValueError("Size metric must be a string like '1024:256'")
    parts = size_metric_str.split(':')
    if len(parts) != 2:
        raise ValueError("Expected exactly one ':' as in 'raw_bytes:compressed_bytes'")
    raw_bytes = float(parts[0])  # non-numeric text raises ValueError
    comp_bytes = float(parts[1])
    if not (math.isfinite(raw_bytes) and math.isfinite(comp_bytes)):
        raise ValueError("Byte counts must be finite numbers")
    if raw_bytes < 0:
        raise ValueError("Raw bytes cannot be negative")
    if comp_bytes <= 0:
        raise ValueError("Compressed bytes must be greater than zero")
    ratio = raw_bytes / comp_bytes
    if not math.isfinite(ratio):
        raise ValueError("Compression ratio is too large to represent")
    return round(ratio, 2)

def lookup_bandwidth_tier_rate(tier_descriptor):
    """
    Looks up rate per GB for egress traffic using the first 3 letters of the tier name.
    Assumes standard tier prefix with at least 3 letters.
    Raises ValueError for unknown tiers.
    """
    if not isinstance(tier_descriptor, str):
        raise ValueError("Tier descriptor must be a string like 'HOT_TIER'")
    prefix = tier_descriptor.strip().upper()[:3]
    tier_rates = {
        "HOT": 0.08,
        "COL": 0.05,
        "ARC": 0.02
    }
    if prefix not in tier_rates:
        raise ValueError(f"Unknown tier {tier_descriptor!r}: must start with HOT, COL or ARC")
    return tier_rates[prefix]

def _run(label, func, prompt):
    print(f"==== Running {func.__name__} ====")
    try:
        print(label, func(input(prompt)))
    except ValueError as err:
        print("Invalid input:", err)


def main():
    _run("", parse_storage_quota, "Enter quota (e.g. 500MB, 10GB, 2TB): ")
    print()
    _run("Compression Ratio:", compute_compression_ratio, "Enter raw:compressed bytes (e.g. 1024:256): ")
    print()
    _run("Rate per GB: $", lookup_bandwidth_tier_rate, "Enter tier descriptor (e.g. HOT_TIER, COLD, ARCHIVE): ")


if __name__ == "__main__":
    main()
