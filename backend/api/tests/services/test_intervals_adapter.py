import asyncio

import pytest

from app.services.intervals import SimulatedIntervalsAdapter


def test_simulated_intervals_normalizes_method_and_period():
    observation = SimulatedIntervalsAdapter().normalize_observation(
        {
            "external_id": "wellness-1",
            "metric_type": "hrv",
            "value": 48.2,
            "unit": "ms",
            "method": "RMSSD",
            "observed_start": "2026-09-20T06:00:00Z",
            "observed_end": "2026-09-20T06:05:00Z",
        }
    )
    assert observation.method == "RMSSD"
    assert observation.unit == "ms"


def test_simulated_intervals_rejects_incomplete_or_reversed_data():
    adapter = SimulatedIntervalsAdapter()
    with pytest.raises(ValueError, match="Faltan campos"):
        adapter.normalize_observation({"external_id": "x"})
    with pytest.raises(ValueError, match="periodo"):
        adapter.normalize_observation(
            {
                "external_id": "x",
                "metric_type": "sleep",
                "value": 1,
                "unit": "hours",
                "method": "provider_estimate",
                "observed_start": "2026-09-20T08:00:00Z",
                "observed_end": "2026-09-20T07:00:00Z",
            }
        )


def test_simulated_intervals_never_mints_real_tokens():
    with pytest.raises(RuntimeError, match="no emite credenciales"):
        asyncio.run(SimulatedIntervalsAdapter().exchange_authorization_code("secret-code"))
