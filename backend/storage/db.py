from __future__ import annotations

from datetime import datetime
from typing import Iterator

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import config


class Base(DeclarativeBase):
    pass


class Scan(Base):
    __tablename__ = "scans"

    id = Column(String, primary_key=True)  # uuid
    module_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="running")  # running|done|error
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    summary_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    partial_result = Column(Boolean, nullable=False, default=False)


class ScanItem(Base):
    __tablename__ = "scan_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False, index=True)
    module_id = Column(String, nullable=False, index=True)
    whitelist_key = Column(String, nullable=False)
    severity = Column(String, nullable=False)  # safe|warning|danger
    title = Column(String, nullable=False)
    detail_json = Column(Text, nullable=False)
    is_new = Column(Boolean, nullable=False, default=False)


class WhitelistEntry(Base):
    __tablename__ = "whitelist_entries"
    __table_args__ = (UniqueConstraint("module_id", "whitelist_key"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    module_id = Column(String, nullable=False, index=True)
    whitelist_key = Column(String, nullable=False)
    label = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ScanDiffLog(Base):
    __tablename__ = "scan_diff_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    module_id = Column(String, nullable=False, index=True)
    whitelist_key = Column(String, nullable=False)
    change_type = Column(String, nullable=False)  # appeared|disappeared
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Database:
    """No1 instance quản lý engine + session scope cho toàn bộ app."""

    def __init__(self, url: str | None = None) -> None:
        self.configure(url or config.database.url)

    def configure(self, url: str) -> None:
        if url.startswith("sqlite:///"):
            path = url.replace("sqlite:///", "", 1)
            if path != ":memory:":
                path = path.lstrip("./")
                if path:
                    from pathlib import Path

                    Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            url,
            connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        )
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self._session_factory()

    def session_scope(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


db = Database()

DATETIME_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def now_iso() -> str:
    return datetime.utcnow().strftime(DATETIME_FMT)


def dt_to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime(DATETIME_FMT)