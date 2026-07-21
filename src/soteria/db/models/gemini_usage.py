"""`gemini_usage_daily` table — self-tracked Gemini API call counter.

Google's Generative Language API doesn't expose real-time quota-remaining;
the only concrete limit numbers this app has ever seen came from a 429
error's message (see chat/usage.py). This table is our own approximate
counter, incremented by chat/gemini_client.py on every call, so the app can
show "N of your daily limit used" without relying on hitting the real limit
to find out.
"""

import datetime

from sqlalchemy import Date, Integer
from sqlalchemy.orm import Mapped, mapped_column

from soteria.db.base import Base


class GeminiUsageDaily(Base):
    __tablename__ = "gemini_usage_daily"

    day: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
