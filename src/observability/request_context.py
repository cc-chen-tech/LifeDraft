"""Request and background-operation correlation context."""

from __future__ import annotations

import re
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token, copy_context
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Iterator, Optional


_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_CURRENT_CONTEXT: ContextVar[Optional["RequestContext"]] = ContextVar(
    "story2_request_context", default=None
)


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    operation_id: Optional[str] = None
    feature: Optional[str] = None
    operation: Optional[str] = None


def resolve_request_id(value: Optional[str]) -> str:
    """Keep a bounded correlation ID or generate a new opaque UUID."""

    candidate = (value or "").strip()
    if _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return uuid.uuid4().hex


def resolve_operation_id(value: Optional[str]) -> str:
    """Keep a bounded operation ID or generate an opaque ID for a request."""

    candidate = (value or "").strip()
    if _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return uuid.uuid4().hex


def current_request_context() -> Optional[RequestContext]:
    return _CURRENT_CONTEXT.get()


def set_request_context(context: RequestContext) -> Token:
    return _CURRENT_CONTEXT.set(context)


def reset_request_context(token: Token) -> None:
    _CURRENT_CONTEXT.reset(token)


@contextmanager
def request_context(context: RequestContext) -> Iterator[RequestContext]:
    token = set_request_context(context)
    try:
        yield context
    finally:
        reset_request_context(token)


def bind_current_context(
    callable_: Callable[..., Any], *args: Any, **kwargs: Any
) -> Callable[[], Any]:
    """Bind the current request context before handing work to a thread pool."""

    context = copy_context()
    return partial(context.run, callable_, *args, **kwargs)
