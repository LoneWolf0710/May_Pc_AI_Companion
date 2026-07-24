"""Weather integration using Open-Meteo API — free, no API key required.

Open-Meteo provides high-quality weather data without any registration.
We fetch current conditions + 3-day forecast for the user's location.

Usage:
    weather = WeatherClient()
    forecast = await weather.get_forecast()  # Uses IP-based geolocation
    forecast = await weather.get_forecast(lat=40.7, lon=-74.0)  # Explicit coords
"""

from __future__ import annotations

import asyncio
import logging
import json
from dataclasses import dataclass

logger = logging.getLogger("may.integrations.weather")

# Open-Meteo endpoints (no API key needed)
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass
class WeatherForecast:
    """Structured weather data."""
    location: str = ""
    temperature: float = 0       # Current temp in Celsius
    feels_like: float = 0        # Feels-like temp
    humidity: int = 0            # Relative humidity %
    wind_speed: float = 0        # km/h
    wind_direction: str = ""     # Cardinal direction
    condition: str = ""          # "Clear sky", "Cloudy", etc.
    condition_icon: str = ""     # WMO weather code mapped to emoji
    uv_index: float = 0
    sunrise: str = ""            # ISO time
    sunset: str = ""             # ISO time
    daily: list[dict] = None     # Next 3 days forecast

    def __post_init__(self):
        if self.daily is None:
            self.daily = []

    def to_dict(self) -> dict:
        return {
            "location": self.location,
            "temperature": self.temperature,
            "feels_like": self.feels_like,
            "humidity": self.humidity,
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction,
            "condition": self.condition,
            "condition_icon": self.condition_icon,
            "uv_index": self.uv_index,
            "sunrise": self.sunrise,
            "sunset": self.sunset,
            "daily": self.daily,
        }

    def to_briefing_text(self) -> str:
        """Format as a natural-language weather briefing for May to deliver."""
        lines = []
        lines.append(f"Currently {self.condition.lower()} and {self.temperature:.0f}C")
        lines.append(f"(feels like {self.feels_like:.0f}C)")
        lines.append(f"Humidity {self.humidity}%, wind {self.wind_speed:.0f} km/h {self.wind_direction}")
        if self.uv_index > 3:
            lines.append(f"UV index is {self.uv_index:.1f} — consider sunscreen")
        if self.daily:
            lines.append("Forecast:")
            for day in self.daily[:3]:
                lines.append(f"  {day.get('date', '?')}: {day.get('condition', '?')} "
                             f"{day.get('temp_min', '?')}-{day.get('temp_max', '?')}C")
        return "\n".join(lines)


# WMO Weather interpretation codes → condition string + emoji
WMO_CODES = {
    0: ("Clear sky", "\u2600\ufe0f"),
    1: ("Mainly clear", "\U0001f324\ufe0f"),
    2: ("Partly cloudy", "\u26c5"),
    3: ("Overcast", "\u2601\ufe0f"),
    45: ("Foggy", "\U0001f32b\ufe0f"),
    48: ("Rime fog", "\U0001f32b\ufe0f"),
    51: ("Light drizzle", "\U0001f326\ufe0f"),
    53: ("Moderate drizzle", "\U0001f326\ufe0f"),
    55: ("Dense drizzle", "\U0001f327\ufe0f"),
    61: ("Slight rain", "\U0001f327\ufe0f"),
    63: ("Moderate rain", "\U0001f327\ufe0f"),
    65: ("Heavy rain", "\U0001f327\ufe0f"),
    71: ("Slight snow", "\U0001f328\ufe0f"),
    73: ("Moderate snow", "\U0001f328\ufe0f"),
    75: ("Heavy snow", "\u2744\ufe0f"),
    80: ("Rain showers", "\U0001f326\ufe0f"),
    81: ("Moderate rain showers", "\U0001f326\ufe0f"),
    82: ("Violent rain showers", "\U0001f326\ufe0f"),
    95: ("Thunderstorm", "\u26c8\ufe0f"),
    96: ("Thunderstorm with hail", "\u26c8\ufe0f"),
    99: ("Thunderstorm with heavy hail", "\u26c8\ufe0f"),
}

# Cardinal wind directions
WIND_DIRS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
             "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


class WeatherClient:
    """Fetches weather from Open-Meteo (free, no API key)."""

    def __init__(self, lat: float | None = None, lon: float | None = None,
                 city: str | None = None):
        self._lat = lat
        self._lon = lon
        self._city = city

    async def _resolve_location(self) -> tuple[float, float, str]:
        """Resolve city name to lat/lon via Open-Meteo geocoding, or use IP geolocation."""
        import httpx

        if self._lat is not None and self._lon is not None:
            return self._lat, self._lon, f"{self._lat:.2f}, {self._lon:.2f}"

        if self._city and self._city.strip():
            # Geocode the city name
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(GEOCODING_URL, params={
                        "name": self._city, "count": 1, "language": "en",
                    })
                    data = resp.json()
                    results = data.get("results", [])
                    if results:
                        r = results[0]
                        return r["latitude"], r["longitude"], r.get("name", self._city)
            except Exception as e:
                logger.warning("Geocoding failed for '%s': %s", self._city, e)

        # Fallback: IP-based geolocation (Open-Meteo doesn't have this,
        # so we use a free IP geolocation service)
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get("https://ipapi.co/json/")
                data = resp.json()
                lat = data.get("latitude", 51.5)  # Default: London
                lon = data.get("longitude", -0.1)
                city = data.get("city", "Unknown")
                return lat, lon, city
        except Exception:
            # Default: London
            return 51.5, -0.1, "London"

    async def get_forecast(self, lat: float | None = None, lon: float | None = None,
                           city: str | None = None) -> WeatherForecast:
        """Get current weather + 3-day forecast.

        Args:
            lat, lon: Explicit coordinates (optional)
            city: City name to geocode (optional)
        """
        import httpx

        # Resolve location
        if lat is not None and lon is not None:
            resolved_lat, resolved_lon, location_name = lat, lon, f"{lat:.2f}, {lon:.2f}"
        else:
            resolved_lat, resolved_lon, location_name = await self._resolve_location()

        # Fetch weather data
        params = {
            "latitude": resolved_lat,
            "longitude": resolved_lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                       "weather_code,wind_speed_10m,wind_direction_10m,uv_index",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                     "sunrise,sunset",
            "timezone": "auto",
            "forecast_days": 3,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(WEATHER_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        current = data.get("current", {})
        daily = data.get("daily", {})

        # Parse current conditions
        wmo_code = current.get("weather_code", 0)
        condition, icon = WMO_CODES.get(wmo_code, ("Unknown", "\u2753"))

        # Wind direction
        wind_deg = current.get("wind_direction_10m", 0)
        wind_idx = round(wind_deg / 22.5) % 16
        wind_dir = WIND_DIRS[wind_idx]

        forecast = WeatherForecast(
            location=location_name,
            temperature=current.get("temperature_2m", 0),
            feels_like=current.get("apparent_temperature", 0),
            humidity=current.get("relative_humidity_2m", 0),
            wind_speed=current.get("wind_speed_10m", 0),
            wind_direction=wind_dir,
            condition=condition,
            condition_icon=icon,
            uv_index=current.get("uv_index", 0),
            sunrise=daily.get("sunrise", [""])[0] if daily.get("sunrise") else "",
            sunset=daily.get("sunset", [""])[0] if daily.get("sunset") else "",
        )

        # Parse daily forecast
        dates = daily.get("time", [])
        codes = daily.get("weather_code", [])
        mins = daily.get("temperature_2m_min", [])
        maxs = daily.get("temperature_2m_max", [])

        for i in range(len(dates)):
            day_code = codes[i] if i < len(codes) else 0
            day_cond, _ = WMO_CODES.get(day_code, ("Unknown", ""))
            forecast.daily.append({
                "date": dates[i],
                "condition": day_cond,
                "temp_min": mins[i] if i < len(mins) else "?",
                "temp_max": maxs[i] if i < len(maxs) else "?",
            })

        logger.info("Weather: %s %.0fC %s", location_name, forecast.temperature, forecast.condition)
        return forecast
