from coursesieve.utils.hashing import build_video_id


def test_video_id_stable() -> None:
    a = build_video_id("input", {"x": 1, "y": 2})
    b = build_video_id("input", {"y": 2, "x": 1})
    assert a == b
