"""Typing bridge for legacy ORM comparisons in SQLAlchemy queries."""

from typing import cast

from sqlalchemy.sql.elements import ColumnElement


def as_sql_condition(value: object) -> ColumnElement[bool]:
    """Keep SQL expressions typed consistently across mypy platforms."""
    return cast(ColumnElement[bool], value)
