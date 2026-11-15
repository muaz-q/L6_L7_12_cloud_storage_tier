"""Lab 6 - code (line) coverage tests for cloud_storage_tier.py.

SRN: PES2UG24AM091 - Mohammed Muaz Iqubal
Goal: execute every line of the module at least once.
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
