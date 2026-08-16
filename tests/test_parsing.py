import io

import pytest
from openpyxl import Workbook

from backend import parsing


def test_parse_csv_semicolon():
    csv = (
        "№;Маршрут (кратко);Общее расстояние, км;Примечания;Год\n"
        "1;Москва – Пекин;5800;перелёт;2023\n"
        "2;Париж – Лондон;340;;2022\n"
    ).encode("utf-8")
    rows = parsing.parse_upload("routes.csv", csv)
    assert len(rows) == 2
    assert rows[0]["route"] == "Москва – Пекин"
    assert rows[0]["year"] == 2023
    assert rows[0]["declared_km"] == 5800.0
    assert rows[0]["note"] == "перелёт"
    assert rows[1]["year"] == 2022
    assert rows[1]["note"] is None


def test_parse_csv_comma():
    csv = "№,Маршрут,Общее расстояние, км,Примечания,Год\n1,Москва – Пекин,5800,,2023\n".encode()
    rows = parsing.parse_upload("routes.csv", csv)
    assert rows[0]["route"] == "Москва – Пекин"


def test_parse_csv_utf8_bom():
    csv = "\ufeff№;Маршрут;Год\n1;Москва – Пекин;2023\n".encode("utf-8")
    rows = parsing.parse_upload("routes.csv", csv)
    assert rows[0]["route"] == "Москва – Пекин"


def test_parse_excel():
    wb = Workbook()
    ws = wb.active
    ws.append(["№", "Маршрут (кратко)", "Общее расстояние, км", "Примечания", "Год"])
    ws.append([1, "Москва – Пекин", 5800, "перелёт", 2023])
    ws.append([2, "Париж – Лондон", 340, None, 2022])
    buf = io.BytesIO()
    wb.save(buf)
    rows = parsing.parse_upload("routes.xlsx", buf.getvalue())
    assert len(rows) == 2
    assert rows[0]["year"] == 2023
    assert rows[1]["declared_km"] == 340.0


def test_parse_missing_route_column():
    with pytest.raises(ValueError):
        parsing.parse_upload("routes.csv", "Foo;Bar\n1;2\n".encode())


def test_parse_unsupported_extension():
    with pytest.raises(ValueError):
        parsing.parse_upload("routes.txt", b"x")
