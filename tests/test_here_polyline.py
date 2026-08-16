from backend.here_polyline import decode_polyline


def test_decode_known_vector():
    # Reference vector from heremaps/flexible-polyline README
    pts = decode_polyline("BFoz5xJ67i1B1B7PzIhaxL7Y")
    expected = [
        (50.1022829, 8.6982122),
        (50.1020076, 8.6956695),
        (50.1006313, 8.6914960),
        (50.0987800, 8.6875156),
    ]
    assert len(pts) == 4
    for (lng, lat), (elat, elng) in zip(pts, expected):
        assert abs(lat - elat) < 1e-5
        assert abs(lng - elng) < 1e-5


def test_decode_invalid_version():
    import pytest

    with pytest.raises(ValueError):
        # header version 0 instead of 1 -> first char 'A' encodes version 0
        decode_polyline("A")
