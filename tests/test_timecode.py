from coursesieve.media.timecode import hms_to_sec, sec_to_hms


def test_roundtrip_timecode() -> None:
    assert sec_to_hms(3661) == "01:01:01"
    assert hms_to_sec("01:01:01") == 3661
