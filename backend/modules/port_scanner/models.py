from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, Column, Integer, ForeignKey

from storage.db import Base


class PortScannerConfig(Base):
    """Bảng cấu hình riêng của module — prefix `port_scanner_` tránh đụng namespace (mục 6.2).

    Lưu cấu hình module đang dùng (scan_mode, danh sách cổng rủi ro) để người
    dùng xem lại / đối chiếu kết quả lịch sử mà không cần mở config.yaml.
    """

    __tablename__ = "port_scanner_config"

    id = Column(String, primary_key=True)
    scan_mode = Column(String, nullable=False)
    known_risky_ports_json = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PortReview(Base):
    __tablename__ = "port_scanner_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_key = Column(String, nullable=False, unique=True)
    endpoint_key = Column(Text, nullable=False)
    fingerprint = Column(String, nullable=False)
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False)
    scope = Column(String, nullable=False)
    note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expired_at = Column(DateTime, nullable=True)
