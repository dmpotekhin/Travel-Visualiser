from backend.analytics import compute_stats


def _segments():
    return [
        {"route_id": 1, "from": "Москва", "to": "Пекин", "transport": "air",
         "distance_km": 5790, "duration_min": 409, "year": 2023},
        {"route_id": 1, "from": "Пекин", "to": "Токио", "transport": "air",
         "distance_km": 2100, "duration_min": 148, "year": 2023},
        {"route_id": 2, "from": "Париж", "to": "Берлин", "transport": "rail",
         "distance_km": 878, "duration_min": 659, "year": 2021},
    ]


def test_totals():
    stats = compute_stats(_segments())
    total = 5790 + 2100 + 878
    assert stats["total_km"] == round(total, 1)
    assert stats["total_miles"] == round(total / 1.609344, 1)
    assert stats["equators"] == round(total / 40075, 1)
    assert stats["moon_distance"] == round(total / 384400, 1)
    assert stats["routes_count"] == 2
    assert stats["segments_count"] == 3
    assert stats["avg_km_per_route"] == round(total / 2, 1)


def test_transport_share():
    stats = compute_stats(_segments())
    air = [x for x in stats["transport_share"] if x["transport"] == "air"][0]
    rail = [x for x in stats["transport_share"] if x["transport"] == "rail"][0]
    assert air["km"] == round(7890, 1)
    assert rail["km"] == round(878, 1)
    assert abs(air["percent"] - round(7890 / (7890 + 878) * 100, 1)) < 0.01


def test_top_cities():
    stats = compute_stats(_segments())
    # Пекин appears twice, others once
    assert stats["top_cities"][0]["city"] == "Пекин"
    assert stats["top_cities"][0]["count"] == 2


def test_year_distribution():
    stats = compute_stats(_segments())
    by_year = {x["year"]: x["km"] for x in stats["year_distribution"]}
    assert by_year[2023] == round(7890, 1)
    assert by_year[2021] == round(878, 1)
