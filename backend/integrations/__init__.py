"""Integrations package — weather, news, calendar, smart home."""

from __future__ import annotations

import logging

logger = logging.getLogger("may.integrations")

# Lazy imports for heavy modules
_weather_client = None
_news_client = None
_calendar_reader = None
_smart_home_client = None
_email_client = None


def get_weather_client(city: str | None = None):
    """Get weather client, optionally configured with a city from settings.

    If city is provided, creates a new client for that city.
    If city is None, uses the cached singleton (IP-based geolocation).
    """
    global _weather_client
    if city:
        from .weather import WeatherClient
        return WeatherClient(city=city)
    if _weather_client is None:
        from .weather import WeatherClient
        _weather_client = WeatherClient()
    return _weather_client


def get_news_client():
    global _news_client
    if _news_client is None:
        from .news import NewsClient
        _news_client = NewsClient()
    return _news_client


def get_calendar_reader():
    global _calendar_reader
    if _calendar_reader is None:
        from .calendar_reader import CalendarReader
        _calendar_reader = CalendarReader()
    return _calendar_reader


def get_smart_home_client():
    global _smart_home_client
    if _smart_home_client is None:
        from .smart_home import SmartHomeClient
        _smart_home_client = SmartHomeClient()
    return _smart_home_client


def get_email_client():
    global _email_client
    if _email_client is None:
        from .email_monitor import EmailClient
        _email_client = EmailClient()
    return _email_client
