from datetime import datetime, timezone
from sqlalchemy import BigInteger, DateTime, Numeric, String, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    entry: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    stop_loss: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    take_profit: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    rr: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="OPEN", index=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)