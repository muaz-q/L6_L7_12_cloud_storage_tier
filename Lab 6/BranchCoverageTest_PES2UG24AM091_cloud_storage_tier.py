"""Lab 6 - branch coverage tests for cloud_storage_tier.py.

SRN: PES2UG24AM091 - Mohammed Muaz Iqubal
Goal: take both the True and False side of every decision, plus boundary values.
"""
import pytest
from cloud_storage_tier import process_storage_tenants, monitor_replication_latency


def bucket(size_gb, egress_gb=0, corrupted=False):
    return {"size_gb": size_gb, "egress_gb": egress_gb, "corrupted": corrupted}


def tenant(tier, buckets, active=True, vault=False):
    return {"account_active": active, "tier": tier,
            "has_backup_vault": vault, "buckets": buckets}


# ---------- process_storage_tenants ----------

def test_single_active_hot_tenant():
    result = process_storage_tenants([tenant("hot", [bucket(100, 50)])], 10.0)
    assert result["total_billed"] == 2.5
    assert result["status"] == "BILLED"


def test_invalid_input_raises():
    with pytest.raises(ValueError):
        process_storage_tenants("not a list", 10.0)


def test_inactive_tenant_is_skipped():
    tenants = [tenant("hot", [bucket(100)], active=False),
               tenant("cool", [bucket(200)])]
    result = process_storage_tenants(tenants, 10.0)
    assert result == {"total_billed": 3.0, "status": "BILLED"}


def test_archive_large_bucket_gets_discount():
    # 1000 GB * 0.005 * 0.90 = 4.50
    result = process_storage_tenants([tenant("archive", [bucket(1000)])], 0.0)
    assert result == {"total_billed": 4.5, "status": "BILLED"}


def test_egress_overage_and_backup_vault_fee():
    # 600*0.025*0.9 = 13.50, egress (150-100)*0.08 = 4.00, vault fee 10.00
    result = process_storage_tenants(
        [tenant("hot", [bucket(600, egress_gb=150)], vault=True)], 10.0)
    assert result == {"total_billed": 27.5, "status": "BILLED"}


def test_unknown_tier_zero_size_and_corrupted_buckets():
    tenants = [tenant("premium", [bucket(100)]),            # unknown tier -> flagged
               tenant("hot", [bucket(0), bucket(50, corrupted=True)])]
    result = process_storage_tenants(tenants, 10.0)
    assert result == {"total_billed": 0.0, "status": "ZERO_USAGE"}


def test_corrupted_archive_bucket_wipes_charge_and_stops():
    buckets = [bucket(100), bucket(50, corrupted=True), bucket(300)]
    result = process_storage_tenants([tenant("archive", buckets)], 10.0)
    assert result == {"total_billed": 0.0, "status": "ZERO_USAGE"}


def test_more_than_four_flags_triggers_audit():
    tenants = [tenant("hot", [bucket(0)] * 5 + [bucket(100)])]
    result = process_storage_tenants(tenants, 10.0)
    assert result == {"total_billed": 2.5, "status": "AUDIT_FLAGGED"}


# ---------- monitor_replication_latency ----------

def test_monitor_no_data():
    assert monitor_replication_latency([]) == "NO_DATA"


def test_monitor_two_consecutive_spikes_alert():
    assert monitor_replication_latency([[100, 250, 300]]) == "SYNC_LAG_ALERT"


def test_monitor_isolated_spikes_stay_synced():
    assert monitor_replication_latency([[250, 100, 250]]) == "SYNCED"


# ---------- extra decision / boundary tests for branch coverage ----------

def test_negative_support_fee_raises():
    # second operand of the `or` in the guard clause
    with pytest.raises(ValueError):
        process_storage_tenants([], -1.0)


def test_empty_tenant_list_is_zero_usage():
    # tenant loop body never runs
    assert process_storage_tenants([], 0.0) == {"total_billed": 0.0, "status": "ZERO_USAGE"}


def test_missing_keys_use_defaults():
    # no account_active key -> treated as inactive
    assert process_storage_tenants([{"tier": "hot"}], 5.0)["status"] == "ZERO_USAGE"
    # active, no tier / buckets / vault keys -> hot tier, no buckets, no fee
    assert process_storage_tenants([{"account_active": True}], 5.0)["status"] == "ZERO_USAGE"
    # bucket with no keys -> size 0 -> flagged, charge 0
    assert process_storage_tenants([tenant("hot", [{}])], 5.0)["status"] == "ZERO_USAGE"


def test_vault_fee_alone_is_billed():
    # tenant with no buckets but a backup vault pays only the support fee
    result = process_storage_tenants([tenant("cool", [], vault=True)], 7.25)
    assert result == {"total_billed": 7.25, "status": "BILLED"}


def test_size_boundary_500_gets_no_discount():
    # size_gb > 500 is False at exactly 500: 500 * 0.025 = 12.50
    assert process_storage_tenants([tenant("hot", [bucket(500)])], 0.0)["total_billed"] == 12.5
    # 501 * 0.025 * 0.90 = 11.2725 -> 11.27
    assert process_storage_tenants([tenant("hot", [bucket(501)])], 0.0)["total_billed"] == 11.27


def test_egress_boundary_100_is_free():
    # egress_gb > 100 is False at exactly 100
    assert process_storage_tenants([tenant("cool", [bucket(100, egress_gb=100)])], 0.0)["total_billed"] == 1.5
    # 101 GB -> 1 GB billed at 0.08
    assert process_storage_tenants([tenant("cool", [bucket(100, egress_gb=101)])], 0.0)["total_billed"] == 1.58


def test_corrupted_non_archive_bucket_still_pays_egress():
    # corrupted hot bucket: storage charge 0, egress (300-100)*0.08 = 16.00
    result = process_storage_tenants([tenant("hot", [bucket(50, egress_gb=300, corrupted=True)])], 0.0)
    assert result == {"total_billed": 16.0, "status": "BILLED"}


def test_corrupted_archive_skips_egress_and_later_buckets_but_not_vault():
    buckets = [bucket(100), bucket(50, egress_gb=500, corrupted=True), bucket(300)]
    result = process_storage_tenants([tenant("archive", buckets, vault=True)], 4.0)
    assert result == {"total_billed": 4.0, "status": "BILLED"}


def test_exactly_four_flags_is_not_audited():
    # flagged_buckets > 4 is False at exactly 4
    tenants = [tenant("hot", [bucket(0)] * 4 + [bucket(100)])]
    assert process_storage_tenants(tenants, 0.0)["status"] == "BILLED"


def test_audit_flag_from_unknown_tiers_with_zero_total():
    # AUDIT_FLAGGED is checked before ZERO_USAGE
    tenants = [tenant("glacier", [bucket(10)]) for _ in range(5)]
    assert process_storage_tenants(tenants, 0.0) == {"total_billed": 0.0, "status": "AUDIT_FLAGGED"}


def test_multiple_tenants_mixed_tiers_sum():
    tenants = [tenant("hot", [bucket(100)]),      # 2.50
               tenant("cool", [bucket(200)]),     # 3.00
               tenant("archive", [bucket(400)])]  # 2.00
    assert process_storage_tenants(tenants, 0.0) == {"total_billed": 7.5, "status": "BILLED"}


@pytest.mark.parametrize("matrix, expected", [
    ([[]], "SYNCED"),                        # node with no readings
    ([[200, 200, 200]], "SYNCED"),           # exactly 200 is not a spike
    ([[201, 201]], "SYNC_LAG_ALERT"),        # just over the threshold
    ([[250], [250]], "SYNCED"),              # streak resets per node
    ([[100, 150], [90, 300, 400]], "SYNC_LAG_ALERT"),  # alert on a later node
    ([[250, 100, 250, 100]], "SYNCED"),      # streak reset after each spike
])
def test_monitor_branches(matrix, expected):
    assert monitor_replication_latency(matrix) == expected


def test_monitor_none_is_no_data():
    assert monitor_replication_latency(None) == "NO_DATA"
