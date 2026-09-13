from datetime import datetime, timedelta, timezone

import pytest
from garmin_fit_sdk import Encoder, Profile

from app.api.routes import parse_fit


def make_fit(sessions=1):
    encoder = Encoder()
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    encoder.on_mesg(Profile['mesg_num']['FILE_ID'], {
        'manufacturer': 'development', 'product': 1, 'type': 'activity', 'time_created': start,
    })
    for second in (0, 5, 10):
        encoder.on_mesg(Profile['mesg_num']['RECORD'], {
            'timestamp': start + timedelta(seconds=second), 'heart_rate': 150,
        })
    for _ in range(sessions):
        encoder.on_mesg(Profile['mesg_num']['SESSION'], {
            'timestamp': start + timedelta(seconds=10), 'start_time': start,
            'total_timer_time': 8, 'total_elapsed_time': 10,
            'avg_heart_rate': 150, 'sport': 'running',
        })
    return bytes(encoder.close())


def test_real_sdk_decodes_generated_fit_with_pauses():
    df, metrics = parse_fit(make_fit())
    assert len(df) == 3
    assert metrics['duration_min'] == pytest.approx(8 / 60)
    assert metrics['avg_hr'] == 150
    assert metrics['trimp_inputs_available']


def test_multisession_is_rejected_instead_of_merging_disciplines():
    with pytest.raises(ValueError, match='multisesión'):
        parse_fit(make_fit(sessions=2))


def test_corrupt_fit_is_rejected():
    content = bytearray(make_fit())
    content[-1] ^= 255
    with pytest.raises(ValueError):
        parse_fit(bytes(content))
