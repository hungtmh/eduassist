"""Trả JSON nhanh: bỏ qua jsonable_encoder của FastAPI cho các endpoint trả dict/list thường.

Đo bằng profiler (loadtest/README.md): với endpoint không khai response_model, FastAPI chạy jsonable_encoder
duyệt đệ quy từng giá trị (~2 triệu lần gọi hàm cho 1.200 request) - khoảng 5 ms CPU mỗi request, phần tốn CPU
nhất của API. FastJSONRoute gói endpoint để trả thẳng FastJSONResponse (orjson, viết bằng Rust), giữ nguyên:
  - mã trạng thái khai ở decorator (status_code=201) hoặc đặt qua tham số `response: Response`,
  - header đặt qua `response: Response` (vd. X-Total-Count của phân trang),
  - cách đổi kiểu như jsonable_encoder: Decimal nguyên -> int, Decimal lẻ -> float, timedelta -> số giây,
    set -> list, ngày giờ -> ISO 8601.
Endpoint có response_model / kiểu trả về, hoặc tự trả Response (SSE...), đi đường cũ của FastAPI.
"""

import functools
import inspect
from datetime import timedelta
from decimal import Decimal
from typing import Any

import orjson
from fastapi import Response
from fastapi.datastructures import DefaultPlaceholder
from fastapi.routing import APIRoute
from pydantic import BaseModel

_OPTIONS = orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY
_HIDDEN = "_fastjson_response"


def _default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        # Giống fastapi.encoders.decimal_encoder
        return int(obj) if obj.as_tuple().exponent >= 0 else float(obj)
    if isinstance(obj, timedelta):
        return obj.total_seconds()
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, bytes):
        return obj.decode()
    raise TypeError(f"Không chuyển được {type(obj).__name__} sang JSON")


def dumps(content: Any) -> bytes:
    return orjson.dumps(content, default=_default, option=_OPTIONS)


class FastJSONResponse(Response):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return dumps(content)


def _wrap(endpoint, status_code: int | None):
    sig = inspect.signature(endpoint)
    params = list(sig.parameters.values())
    # FastAPI chỉ tiêm Response cho MỘT tham số: endpoint đã có `response: Response` thì đọc luôn tham số đó,
    # chưa có thì thêm một tham số ẩn (không hiện trong tài liệu API vì FastAPI không coi Response là input)
    own = next((p.name for p in params if p.annotation is Response), None)
    key = own or _HIDDEN
    if own:
        new_sig = sig
    else:
        hidden = inspect.Parameter(_HIDDEN, inspect.Parameter.KEYWORD_ONLY, annotation=Response)
        # Tham số **kwargs (nếu có) phải đứng cuối
        at = next((i for i, p in enumerate(params) if p.kind is inspect.Parameter.VAR_KEYWORD), len(params))
        new_sig = sig.replace(parameters=[*params[:at], hidden, *params[at:]])

    def take(kwargs: dict) -> Response:
        return kwargs[key] if own else kwargs.pop(key)

    def finish(result: Any, sub: Response) -> Any:
        if isinstance(result, Response):
            return result
        # FastAPI tiêm cùng một đối tượng Response cho mọi tham số kiểu Response: header / mã trạng thái
        # mà endpoint đặt lên `response` nằm ở đây
        resp = FastJSONResponse(result, status_code=sub.status_code or status_code or 200)
        resp.headers.raw.extend(h for h in sub.headers.raw if h[0].lower() != b"content-length")
        return resp

    if inspect.iscoroutinefunction(endpoint):

        @functools.wraps(endpoint)
        async def wrapper(*args, **kwargs):
            sub = take(kwargs)
            return finish(await endpoint(*args, **kwargs), sub)

    else:

        @functools.wraps(endpoint)
        def wrapper(*args, **kwargs):  # vẫn là def thường -> FastAPI chạy trong thread pool như cũ
            sub = take(kwargs)
            return finish(endpoint(*args, **kwargs), sub)

    wrapper.__signature__ = new_sig
    return wrapper


class FastJSONRoute(APIRoute):
    def __init__(self, path: str, endpoint, **kwargs):
        response_model = kwargs.get("response_model")
        no_model = response_model is None or isinstance(response_model, DefaultPlaceholder)
        no_annotation = inspect.signature(endpoint).return_annotation is inspect.Signature.empty
        if no_model and no_annotation:
            endpoint = _wrap(endpoint, kwargs.get("status_code"))
        super().__init__(path, endpoint, **kwargs)
