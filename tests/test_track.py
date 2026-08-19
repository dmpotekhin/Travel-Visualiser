import pytest

from backend import track


GPX = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>Demo</name>
    <trkseg>
      <trkpt lat="59.9311" lon="30.3609"></trkpt>
      <trkpt lat="55.7558" lon="37.6173"></trkpt>
      <trkpt lat="39.9042" lon="116.4074"></trkpt>
    </trkseg>
  </trk>
</gpx>
"""


KML = b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <LineString>
        <coordinates>
          30.3609,59.9311,0
          37.6173,55.7558,0
          116.4074,39.9042,0
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""

GEOJSON = b"""{
  "type": "FeatureCollection",
  "features": [
    {"type": "Feature", "properties": {},
     "geometry": {"type": "LineString", "coordinates": [
        [30.3609, 59.9311], [37.6173, 55.7558], [116.4074, 39.9042]
     ]}}
  ]
}
"""


def test_parse_gpx():
    pts = track.parse_gpx(GPX)
    assert len(pts) == 3
    assert pts[0] == [30.3609, 59.9311]
    assert pts[-1] == [116.4074, 39.9042]


def test_parse_kml():
    pts = track.parse_kml(KML)
    assert len(pts) == 3
    assert pts[0] == [30.3609, 59.9311]


def test_parse_geojson():
    pts = track.parse_geojson(GEOJSON)
    assert len(pts) == 3
    assert pts[-1] == [116.4074, 39.9042]


def test_parse_track_dispatch():
    assert len(track.parse_track(GPX, "r.gpx")) == 3
    assert len(track.parse_track(KML, "r.kml")) == 3
    assert len(track.parse_track(GEOJSON, "r.geojson")) == 3
    with pytest.raises(ValueError):
        track.parse_track(b"", "r.csv")


def test_parse_gpx_rejects_empty():
    with pytest.raises(ValueError):
        track.parse_gpx(b"<gpx></gpx>")


def test_parse_gmaps_url():
    url = "https://www.google.com/maps/dir/59.9311,30.3609/55.7558,37.6173/39.9042,116.4074"
    pts = track.parse_gmaps_url(url)
    assert len(pts) == 3
    assert pts[0] == [30.3609, 59.9311]
    assert pts[-1] == [116.4074, 39.9042]


def test_parse_gmaps_url_rejects():
    with pytest.raises(ValueError):
        track.parse_gmaps_url("https://maps.google.com/?q=paris")


def test_auto_transport():
    assert track.auto_transport(5000) == "air"
    assert track.auto_transport(500) == "rail"
    assert track.auto_transport(100) == "car"
    assert track.auto_transport(5) == "foot"


def test_simplify_keeps_endpoints():
    line = [[float(i), 0.0] for i in range(50)]
    s = track.simplify(line, tolerance_km=0.01)
    assert s[0] == line[0]
    assert s[-1] == line[-1]


def test_simplify_to_caps_points():
    line = [[float(i), 0.0] for i in range(500)]
    s = track.simplify_to(line, max_points=24)
    assert len(s) <= 24
    assert s[0] == line[0]
    assert s[-1] == line[-1]


def test_coords_to_segments():
    coords = [[30.3609, 59.9311], [37.6173, 55.7558], [116.4074, 39.9042]]
    segs = track.coords_to_segments(coords, transport="car")
    assert len(segs) == 2
    assert segs[0]["from"] == "Точка 1" and segs[0]["to"] == "Точка 2"
    assert segs[0]["transport"] == "car"
    assert segs[0]["distance_km"] > 0
    assert segs[1]["geometry"] == [[37.6173, 55.7558], [116.4074, 39.9042]]


def test_coords_to_segments_auto():
    coords = [[30.3609, 59.9311], [116.4074, 39.9042]]  # ~6000 km -> air
    segs = track.coords_to_segments(coords, transport="auto")
    assert segs[0]["transport"] == "air"
