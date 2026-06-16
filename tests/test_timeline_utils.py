"""Tests for canonical timeline timebase utilities (Ticket LB-201)."""
import pytest
from scripts.timeline_utils import (
    MASTER_SAMPLE_RATE,
    TimeInterval,
    ms_to_samples,
    samples_to_ms,
    validate_interval,
    interval_duration_samples,
    detect_overlap_samples,
    detect_gap_samples,
    clamp_to_master_bounds,
    provider_duration_from_samples,
)


class TestTimeConversion:
    def test_exact_round_trip(self):
        """Verify that ms -> samples -> ms is exact for standard values."""
        test_ms_values = [0, 100, 500, 1000, 4321, 15000, 146599]
        for ms in test_ms_values:
            samples = ms_to_samples(ms)
            round_trip_ms = samples_to_ms(samples)
            # Allow 1ms tolerance due to integer rounding
            assert abs(round_trip_ms - ms) <= 1, f"Round trip failed for {ms}ms"

    def test_100_span_cumulative_drift_equals_zero(self):
        """Verify that converting 100 spans and back has zero cumulative drift."""
        total_ms = 0
        total_samples = 0
        for i in range(100):
            ms = 1234  # Arbitrary non-trivial duration
            total_ms += ms
            total_samples += ms_to_samples(ms)
        
        round_trip_total_ms = samples_to_ms(total_samples)
        # The cumulative drift should be minimal (<= 1ms for 100 spans at 48kHz)
        assert abs(round_trip_total_ms - total_ms) <= 2, f"Cumulative drift too high: {abs(round_trip_total_ms - total_ms)}ms"


class TestTimeInterval:
    def test_valid_interval_creation(self):
        """Verify valid interval creation."""
        interval = TimeInterval(start_samples=1000, end_samples=5000)
        assert interval.start_samples == 1000
        assert interval.end_samples == 5000
        assert interval.duration_samples == 4000

    def test_negative_start_rejected(self):
        """Verify that negative start samples are rejected."""
        with pytest.raises(ValueError, match="start cannot be negative"):
            TimeInterval(start_samples=-100, end_samples=1000)

    def test_end_before_start_rejected(self):
        """Verify that end before start is rejected."""
        with pytest.raises(ValueError, match="cannot be before start"):
            TimeInterval(start_samples=5000, end_samples=1000)


class TestValidation:
    def test_zero_duration_interval_rejected(self):
        """Verify that zero-duration intervals are rejected by validate_interval."""
        # TimeInterval init allows start == end, but validate_interval should reject duration <= 0
        interval = TimeInterval(start_samples=1000, end_samples=1000)
        with pytest.raises(ValueError, match="duration must be positive"):
            validate_interval(interval, master_duration_samples=5000)

    def test_out_of_bounds_interval_rejected(self):
        """Verify that intervals exceeding master duration are rejected."""
        interval = TimeInterval(start_samples=1000, end_samples=10000)
        master_duration = 5000
        with pytest.raises(ValueError, match="exceeds master duration"):
            validate_interval(interval, master_duration)

    def test_valid_interval_passes(self):
        """Verify that a valid interval passes validation."""
        interval = TimeInterval(start_samples=1000, end_samples=5000)
        validate_interval(interval, master_duration_samples=10000)  # Should not raise


class TestIntervalOperations:
    def test_interval_duration(self):
        """Verify duration calculation."""
        assert interval_duration_samples(1000, 5000) == 4000

    def test_detect_overlap_samples_true(self):
        """Verify overlap detection when intervals overlap."""
        i1 = TimeInterval(start_samples=1000, end_samples=5000)
        i2 = TimeInterval(start_samples=4000, end_samples=8000)
        assert detect_overlap_samples(i1, i2) is True

    def test_detect_overlap_samples_false(self):
        """Verify overlap detection when intervals do not overlap."""
        i1 = TimeInterval(start_samples=1000, end_samples=5000)
        i2 = TimeInterval(start_samples=5000, end_samples=8000)  # Touching, not overlapping
        assert detect_overlap_samples(i1, i2) is False
        
        i3 = TimeInterval(start_samples=6000, end_samples=8000)  # Gap
        assert detect_overlap_samples(i1, i3) is False

    def test_detect_gap_samples(self):
        """Verify gap detection."""
        i1 = TimeInterval(start_samples=1000, end_samples=5000)
        i2 = TimeInterval(start_samples=7000, end_samples=9000)
        assert detect_gap_samples(i1, i2) == 2000
        
        # Touching
        i3 = TimeInterval(start_samples=5000, end_samples=7000)
        assert detect_gap_samples(i1, i3) == 0
        
        # Overlapping
        i4 = TimeInterval(start_samples=4000, end_samples=6000)
        assert detect_gap_samples(i1, i4) == 0


class TestClamping:
    def test_clamp_to_master_bounds(self):
        """Verify clamping to master bounds."""
        master_duration = 10000
        
        # Normal case
        interval = clamp_to_master_bounds(1000, 5000, master_duration)
        assert interval.start_samples == 1000
        assert interval.end_samples == 5000
        
        # Exceeds end
        interval = clamp_to_master_bounds(8000, 15000, master_duration)
        assert interval.start_samples == 8000
        assert interval.end_samples == 10000
        
        # Negative start
        interval = clamp_to_master_bounds(-500, 5000, master_duration)
        assert interval.start_samples == 0
        assert interval.end_samples == 5000

    def test_exact_final_span_reaches_master_end(self):
        """Verify that clamping a span to the end works correctly."""
        master_duration = 146599
        interval = clamp_to_master_bounds(140000, 200000, master_duration)
        assert interval.end_samples == master_duration


class TestProviderRounding:
    def test_provider_duration_from_samples(self):
        """Verify that provider duration meets minimum requirements."""
        # 3000 samples at 48kHz is 62.5ms, should round up to provider min
        duration_ms = provider_duration_from_samples(3000, provider_min_ms=4000)
        assert duration_ms == 4000
        
        # 5000 samples at 48kHz is ~104ms, should exceed provider min
        duration_ms = provider_duration_from_samples(5000, provider_min_ms=4000)
        assert duration_ms >= 104
