"""FastJSONRoute phải trả đúng như đường cũ của FastAPI (jsonable_encoder), chỉ nhanh hơn."""

import json
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, FastAPI, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from eduassist.api.fastjson import FastJSONRoute, dumps
from eduassist.services.core import Page

VN = timezone(timedelta(hours=7))
SAMPLE = {
    "nguyen": Decimal("6500000"),
    "le": Decimal("12.5"),
    "ngay": date(2026, 11, 14),
    "luc": datetime(2026, 11, 14, 9, 30, 15, 123456, tzinfo=VN),
    "luc_utc": datetime(2026, 11, 14, 2, 30, tzinfo=UTC),
    "gio": time(18, 30),
    "khoang": timedelta(minutes=90),
    "tap": {"a"},
    "long": [{"x": None, "y": True, "z": [1, 2.5, "chữ có dấu"]}],
    3: "khoá số",
}


def test_dumps_matches_jsonable_encoder():
    assert json.loads(dumps(SAMPLE)) == json.loads(json.dumps(jsonable_encoder(SAMPLE)))


def _app() -> FastAPI:
    router = APIRouter(route_class=FastJSONRoute)

    @router.get("/sync")
    def sync_page(response: Response):
        page = Page([{"id": 1, "so_tien": Decimal("100")}], 42)
        response.headers["X-Total-Count"] = str(page.total)
        return page

    @router.get("/async")
    async def async_dict():
        return {"ok": True, "ngay": date(2026, 1, 2)}

    @router.post("/created", status_code=201)
    def created(ten: str):
        return {"ten": ten}

    @router.get("/status-from-response")
    def custom_status(response: Response):
        response.status_code = 202
        return {"accepted": True}

    @router.get("/own-response")
    def own():
        return PlainTextResponse("tự trả")

    @router.get("/typed")
    def typed() -> dict[str, int]:  # có kiểu trả về -> đi đường cũ của FastAPI
        return {"a": 1}

    app = FastAPI()
    app.include_router(router)
    return app


def test_route_keeps_status_headers_and_values():
    c = TestClient(_app())
    r = c.get("/sync")
    assert r.status_code == 200 and r.headers["x-total-count"] == "42"
    assert r.headers["content-type"] == "application/json"
    assert r.json() == [{"id": 1, "so_tien": 100}]

    assert c.get("/async").json() == {"ok": True, "ngay": "2026-01-02"}

    r = c.post("/created", params={"ten": "Lan"})
    assert r.status_code == 201 and r.json() == {"ten": "Lan"}

    r = c.get("/status-from-response")
    assert r.status_code == 202 and r.json() == {"accepted": True}

    assert c.get("/own-response").text == "tự trả"
    assert c.get("/typed").json() == {"a": 1}


def test_wrapped_endpoint_keeps_query_validation_and_openapi():
    c = TestClient(_app())
    assert c.post("/created").status_code == 422  # thiếu tham số bắt buộc vẫn bị FastAPI chặn
    params = {p["name"] for p in c.get("/openapi.json").json()["paths"]["/created"]["post"]["parameters"]}
    assert params == {"ten"}  # tham số ẩn để lấy Response không lộ ra tài liệu API
