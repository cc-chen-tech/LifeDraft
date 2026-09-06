from sqlalchemy import inspect

from src.database.models import User


def test_module_reset_clears_rows_and_reuses_schema(db_engine, clear_isolated_db):
    with db_engine.begin() as connection:
        connection.execute(
            User.__table__.insert().values(
                private_id="isolation-private",
                public_id="isolate",
                display_name="Isolation",
            )
        )

    clear_isolated_db(db_engine)

    assert inspect(db_engine).has_table("users")
    with db_engine.begin() as connection:
        assert connection.execute(User.__table__.select()).fetchall() == []
        inserted = connection.execute(
            User.__table__.insert().values(
                private_id="isolation-private-2",
                public_id="isolat2",
                display_name="Isolation 2",
            )
        ).inserted_primary_key

    assert inserted[0] == 1
