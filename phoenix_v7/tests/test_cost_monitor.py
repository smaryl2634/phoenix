import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from guardrails.cost_monitor import CostMonitor


def test_fresh_monitor_is_not_over_limit():
    with tempfile.TemporaryDirectory() as d:
        mon = CostMonitor(storage_path=Path(d) / "cost.json")
        assert mon.is_over_limit(daily_limit=5.0, monthly_limit=50.0) is False


def test_recording_pushes_over_daily_limit():
    with tempfile.TemporaryDirectory() as d:
        mon = CostMonitor(storage_path=Path(d) / "cost.json")
        mon.record(3.0)
        mon.record(3.0)
        assert mon.is_over_limit(daily_limit=5.0, monthly_limit=50.0) is True


def test_persists_across_instances():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "cost.json"
        CostMonitor(storage_path=path).record(4.0)
        mon2 = CostMonitor(storage_path=path)
        assert mon2.is_over_limit(daily_limit=5.0, monthly_limit=50.0) is False
        mon2.record(2.0)
        assert mon2.is_over_limit(daily_limit=5.0, monthly_limit=50.0) is True


def test_daily_total_sums_recent_entries():
    with tempfile.TemporaryDirectory() as d:
        monitor = CostMonitor(storage_path=Path(d) / "cost.json")
        monitor.record(1.5)
        monitor.record(2.5)
        assert monitor.daily_total() == 4.0


def test_monthly_total_sums_recent_entries():
    with tempfile.TemporaryDirectory() as d:
        monitor = CostMonitor(storage_path=Path(d) / "cost.json")
        monitor.record(1.0)
        monitor.record(2.0)
        assert monitor.monthly_total() == 3.0


def test_daily_total_zero_when_no_entries():
    with tempfile.TemporaryDirectory() as d:
        monitor = CostMonitor(storage_path=Path(d) / "cost.json")
        assert monitor.daily_total() == 0.0
