from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from lognix.db import Base


class Setting(Base):
    """Chave/valor global. `value_enc` guarda segredos; `value` guarda o resto."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
