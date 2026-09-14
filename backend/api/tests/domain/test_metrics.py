import pytest

from app.domain.metrics import calculate_banister_trimp, calculate_ewma, calculate_training_status, calculate_tss
from app.services.data_processing import clean_telemetry_to_dataframe
from app.services.physiology import extract_session_metrics


def records():
    return [
        {"timestamp": "2026-09-01T00:00:00Z", "heart_rate": 150},
        {"timestamp": "2026-09-01T00:00:05Z", "heart_rate": None},
        {"timestamp": "2026-09-01T00:00:10Z", "heart_rate": 160},
    ]


def test_irregular_sampling_uses_elapsed_time_without_inventing_timer():
    df = clean_telemetry_to_dataframe(records())
    result = extract_session_metrics(df)
    assert result["duration_min"] == pytest.approx(10 / 60)
    assert result["duration_source"] == "record_elapsed"
    assert not result["trimp_inputs_available"]
    assert df.heart_rate.isna().sum() == 1


def test_timer_summary_excludes_pauses_and_precedes_record_mean():
    result = extract_session_metrics(clean_telemetry_to_dataframe(records()), {
        "total_timer_time": 8, "avg_heart_rate": 151, "max_heart_rate": 165,
    })
    assert result["duration_min"] == pytest.approx(8 / 60)
    assert result["avg_hr"] == 151
    assert result["trimp_inputs_available"]


def test_missing_hr_does_not_erase_duration():
    df = clean_telemetry_to_dataframe([{ "timestamp": r["timestamp"] } for r in records()])
    result = extract_session_metrics(df)
    assert result["avg_hr"] is None
    assert result["max_hr"] is None
    assert result["duration_min"] > 0


def test_sort_and_deduplicate_without_changing_utc_instant():
    data = records()
    df = clean_telemetry_to_dataframe([data[2], data[0], data[1], data[2]])
    assert len(df) == 3
    assert df.timestamp.is_monotonic_increasing
    assert str(df.timestamp.dt.tz) == "UTC"


@pytest.mark.parametrize("data", [[], [{"heart_rate": 150}], [{"timestamp": "bad"}], [{"timestamp": None}]])
def test_invalid_timestamps_rejected(data):
    with pytest.raises(ValueError):
        clean_telemetry_to_dataframe(data)


@pytest.mark.parametrize("is_male,expected", [(True, 50.14), (False, 59.46)])
def test_classic_trimp_reference_values(is_male, expected):
    # 60 min, reserva utilizada 50%; valores de referencia redondeados.
    assert calculate_banister_trimp(60, 125, 50, 200, is_male) == expected


@pytest.mark.parametrize("rest,maximum,average", [(100, 100, 120), (100, 90, 120), (50, 190, 200), (50, 190, float("nan"))])
def test_invalid_profile_or_hr_rejected(rest, maximum, average):
    with pytest.raises(ValueError):
        calculate_banister_trimp(60, average, rest, maximum, True)


def test_day_of_rest_decays_load_and_tsb_uses_previous_day():
    result = calculate_training_status(0, 42, 70)
    assert result == {"ctl": 41, "atl": 60, "tsb": -28}
    assert calculate_ewma(100, 100, 42) == 100


def test_hour_at_ftp_is_100_tss():
    assert calculate_tss(3600, 250, 250) == 100
    with pytest.raises(ValueError):
        calculate_tss(3600, 250, 0)
