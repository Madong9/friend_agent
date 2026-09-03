from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base, build_engine
from backend.app.models import User


def test_user_model_round_trip():
    engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(
                User(
                    id="u1",
                    nickname="阿青",
                    campus="西区",
                    grade="研一",
                    major="计算机",
                )
            )
            db.commit()
            user = db.get(User, "u1")
            assert user is not None
            assert user.interests == []
            assert user.token_version == 0
    finally:
        engine.dispose()


def test_sqlite_foreign_keys_are_enabled():
    engine = build_engine("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    finally:
        engine.dispose()
