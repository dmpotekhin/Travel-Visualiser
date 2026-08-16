from backend import geo


def test_haversine_moscow_spb():
    d = geo.haversine_km(55.7558, 37.6173, 59.9311, 30.3609)
    assert 600 < d < 700


def test_haversine_zero():
    assert geo.haversine_km(10.0, 20.0, 10.0, 20.0) == 0.0


def test_geodesic_points_endpoints():
    pts = geo.geodesic_points(55.7558, 37.6173, 59.9311, 30.3609, n=10)
    assert len(pts) == 11
    assert abs(pts[0][0] - 37.6173) < 1e-6
    assert abs(pts[0][1] - 55.7558) < 1e-6
    assert abs(pts[-1][0] - 30.3609) < 1e-6
    assert abs(pts[-1][1] - 59.9311) < 1e-6


def test_geodesic_same_point():
    pts = geo.geodesic_points(10.0, 20.0, 10.0, 20.0, n=5)
    assert pts[0] == [20.0, 10.0]
