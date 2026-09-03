from __future__ import annotations

from sqlalchemy import JSON, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    campus: Mapped[str] = mapped_column(String(64), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    time: Mapped[str] = mapped_column(String(128), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    capacity: Mapped[int] = mapped_column(Integer, default=20)
    public: Mapped[bool] = mapped_column(Boolean, default=True)
