from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, Column

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