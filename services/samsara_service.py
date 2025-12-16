"""
Samsara API service for FleetMaster Bot
Centralised API logic, pagination, and background refresh loop.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from config import settings
from utils.helpers import meters_to_miles, parse_series_value_and_time
from utils.logger import get_logger

logger = get_logger("services.samsara_service")


class SamsaraService:
    def __init__(self):
        self.base_url = settings.SAMSARA_BASE_URL.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {settings.SAMSARA_API_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Session State
        self.session: aiohttp.ClientSession | None = None
        self._session_refs = 0  # Reference counter for nested usage
        self._session_lock = asyncio.Lock()  # Prevent race conditions during init

        # Cache State
        self._vehicle_cache: list[dict[str, Any]] | None = None
        self._cache_timestamp: datetime | None = None
        self._cache_duration = timedelta(minutes=3)

        # Background Loop State
        self._running = False
        self._interval = 3600  # 1 hour

    # -----------------------------
    # Context Management (Ref-Counted)
    # -----------------------------
    async def __aenter__(self):
        """
        Initializes the session if it doesn't exist, or reuses it.
        Increments reference counter.
        """
        async with self._session_lock:
            if self.session is None or self.session.closed:
                connector = aiohttp.TCPConnector(limit=20, limit_per_host=10)
                timeout = aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)
                self.session = aiohttp.ClientSession(
                    headers=self.headers, timeout=timeout, connector=connector
                )
                logger.info("🔌 Created new Samsara session")

            self._session_refs += 1
            return self

    async def __aexit__(self, exc_type, exc, tb):
        """
        Decrements reference counter.
        Only closes the session if refs == 0.
        """
        async with self._session_lock:
            self._session_refs -= 1
            if self._session_refs <= 0:
                await self.close_session()

    async def close_session(self):
        """Force close the session."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("🔒 Closed Samsara session")
        self.session = None
        self._session_refs = 0

    # -----------------------------
    # Internal Helpers
    # -----------------------------
    def _is_cache_valid(self) -> bool:
        if not self._vehicle_cache or not self._cache_timestamp:
            return False
        return datetime.utcnow() - self._cache_timestamp < self._cache_duration

    def _cache_vehicles(self, vehicles: list[dict[str, Any]]) -> None:
        self._vehicle_cache = vehicles
        self._cache_timestamp = datetime.utcnow()
        logger.info(f"🗃️ Cached {len(vehicles)} vehicles")

    # -----------------------------
    # Core Request Logic
    # -----------------------------
    async def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        max_retries: int = 2,
    ) -> dict[str, Any] | None:
        # Auto-connect if session is missing (Safety net)
        if not self.session or self.session.closed:
            logger.warning("Session missing/closed in _make_request. Attempting auto-connect.")
            # This is a fallback; ideally caller uses 'async with'
            async with self:
                return await self._make_request(endpoint, method, params, json, max_retries)

        url = f"{self.base_url}{endpoint}"

        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Request {method} {url} (attempt {attempt + 1})")
                async with self.session.request(method, url, params=params, json=json) as resp:
                    if resp.status == 200:
                        return await resp.json()

                    if resp.status in (401, 403):
                        logger.error(f"🚫 Auth error ({resp.status})")
                        return None

                    if resp.status == 429 and attempt < max_retries:
                        wait = 2 ** (attempt + 1)  # Exponential backoff
                        logger.warning(f"Rate limited; retrying in {wait}s")
                        await asyncio.sleep(wait)
                        continue

                    text = await resp.text()
                    logger.error(f"API error {resp.status}: {text}")
                    return None

            except aiohttp.ClientError as e:
                logger.error(f"Network error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error: {e}")

            if attempt < max_retries:
                await asyncio.sleep(1)

        return None

    # -----------------------------
    # Vehicle Operations
    # -----------------------------
    async def get_vehicles(self, use_cache: bool = True) -> list[dict[str, Any]]:
        if use_cache and self._is_cache_valid() and self._vehicle_cache:
            logger.debug("Returning vehicles from cache")
            return self._vehicle_cache

        logger.info("Fetching vehicles (paginated)")
        vehicles: list[dict[str, Any]] = []
        params = {"types": "light_duty,medium_duty,heavy_duty"}
        endpoint = "/fleet/vehicles"
        cursor = None

        while True:
            if cursor:
                params["after"] = cursor

            result = await self._make_request(endpoint, params=params)
            if not result or "data" not in result:
                break

            batch = result.get("data", [])
            vehicles.extend(batch)

            pagination = result.get("pagination", {}) or {}
            if not pagination.get("hasNextPage"):
                break

            cursor = pagination.get("endCursor")
            if not cursor:
                break

        self._cache_vehicles(vehicles)
        return vehicles

    async def get_vehicle_by_id(self, vehicle_id: str) -> dict[str, Any] | None:
        if self._is_cache_valid() and self._vehicle_cache:
            for v in self._vehicle_cache:
                if str(v.get("id")) == str(vehicle_id):
                    return v

        result = await self._make_request(f"/fleet/vehicles/{vehicle_id}")
        if result and "data" in result:
            return result["data"]

        # Fallback: Refresh list if not found
        vehicles = await self.get_vehicles(use_cache=False)
        for v in vehicles:
            if str(v.get("id")) == str(vehicle_id):
                return v
        return None

    async def get_vehicle_odometer_stats(
        self, vehicle_ids: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        params = {"types": "obdOdometerMeters"}
        if vehicle_ids:
            # Join IDs safely
            params["vehicleIds"] = ",".join([str(x) for x in vehicle_ids][:50])

        result = await self._make_request("/fleet/vehicles/stats/feed", params=params)

        data: dict[str, dict[str, Any]] = {}
        if not result or "data" not in result:
            logger.warning("No odometer data from API")
            return data

        stats = result["data"] or []
        for s in stats:
            vid = s.get("id")
            if not vid:
                continue
            series = s.get("obdOdometerMeters")
            meters, ts = parse_series_value_and_time(series)

            if meters is None:
                continue

            miles = meters_to_miles(meters)
            # Handle nested externalIds safely
            vin = s.get("externalIds", {}).get("samsara.vin") or s.get("vin")

            data[str(vid)] = {"vin": vin, "odometer": miles, "lastUpdated": ts}
        return data

    async def get_vehicle_location(self, vehicle_id: str) -> dict[str, Any] | None:
        params = {"types": "gps", "vehicleIds": str(vehicle_id)}
        result = await self._make_request("/fleet/vehicles/stats/feed", params=params)

        if not result or "data" not in result:
            logger.warning(f"No GPS data for vehicle {vehicle_id}")
            return None

        for s in result.get("data", []):
            if str(s.get("id")) != str(vehicle_id):
                continue

            gps_list = s.get("gps")
            if not gps_list or not isinstance(gps_list, list):
                continue

            last = gps_list[-1]
            lat = last.get("latitude")
            lng = last.get("longitude")
            ts = last.get("time") or last.get("timestamp")
            address = last.get("reverseGeo", {}).get("formattedLocation")

            if lat is not None and lng is not None:
                return {
                    "latitude": lat,
                    "longitude": lng,
                    "time": ts,
                    "address": address,
                }

        logger.warning(f"No valid GPS found for vehicle {vehicle_id}")
        return None

    # -----------------------------
    # Vehicle Search & Detailed Info
    # -----------------------------
    async def search_vehicles(
        self, query: str, search_by: str = "name", limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Search vehicles by name, VIN, or plate number.
        """
        # Always try cache first, but allow refresh if empty
        vehicles = await self.get_vehicles(use_cache=True)
        if not vehicles:
            logger.warning("No vehicles available for search.")
            return []

        q = query.lower().strip()
        results = []

        for v in vehicles:
            name = (v.get("name") or "").lower()
            # Safely get VIN from various possible locations
            vin = (v.get("vin") or v.get("externalIds", {}).get("samsara.vin", "")).lower()
            plate = (v.get("licensePlate") or "").lower()

            if (
                (search_by in ("name", "all") and q in name)
                or (search_by in ("vin", "all") and q in vin)
                or (search_by in ("plate", "all") and q in plate)
            ):
                results.append(v)
                if len(results) >= limit:
                    break

        logger.info(f"🔍 Search '{query}' matched {len(results)} vehicles")
        return results

    async def get_vehicle_with_stats(self, vehicle_id: str) -> dict[str, Any] | None:
        """
        Return a vehicle with odometer + VIN + latest update timestamp.
        """
        vehicle = await self.get_vehicle_by_id(vehicle_id)
        if not vehicle:
            logger.warning(f"Vehicle {vehicle_id} not found.")
            return None

        try:
            # Wrap odometer fetch in timeout to prevent hanging UI
            odos = await asyncio.wait_for(
                self.get_vehicle_odometer_stats([vehicle_id]), timeout=6.0
            )
            odo = odos.get(str(vehicle_id))
            if odo:
                vehicle["odometer"] = odo.get("odometer")
                vehicle["vin"] = odo.get("vin") or vehicle.get("vin")
                vehicle["lastUpdated"] = odo.get("lastUpdated") or vehicle.get("updatedAt")
        except asyncio.TimeoutError:
            logger.warning(f"Odometer fetch for {vehicle_id} timed out.")
        except Exception as e:
            logger.error(f"Error while getting stats for {vehicle_id}: {e}")

        return vehicle

    # -----------------------------
    # General Utilities
    # -----------------------------
    def clear_cache(self) -> None:
        self._vehicle_cache = None
        self._cache_timestamp = None
        logger.info("🧹 Cleared vehicle cache")

    async def test_connection(self) -> bool:
        r = await self._make_request("/fleet/vehicles", params={"limit": 1})
        ok = r is not None
        if ok:
            logger.info("✅ Samsara connection OK")
        else:
            logger.error("❌ Samsara connection failed")
        return ok

    # -----------------------------
    # Background Loop
    # -----------------------------
    async def run_forever(self):
        """
        Continuously refresh vehicle cache.
        Uses the shared session context properly.
        """
        if self._running:
            logger.warning("⚠️ SamsaraService loop already running")
            return

        self._running = True
        logger.info("🔄 Starting Samsara auto-refresh loop")

        try:
            # 'async with self' now safely increments ref count
            async with self:
                while self._running:
                    try:
                        await self.get_vehicles(use_cache=False)
                        logger.info("✅ Refreshed vehicle cache successfully")
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        logger.error(f"💥 Error inside Samsara loop: {e}")

                    # Sleep in small chunks to allow faster shutdown check?
                    # Or just sleep:
                    await asyncio.sleep(self._interval)

        except asyncio.CancelledError:
            logger.info("🛑 SamsaraService loop cancelled gracefully")
        except Exception as e:
            logger.error(f"Critical Samsara loop crash: {e}")
        finally:
            self._running = False
            # __aexit__ is called automatically by 'async with',
            # decrementing the ref count.
            logger.info("🔒 Samsara loop stopped")


# =====================================================
# Singleton instance for global import
# =====================================================
samsara_service = SamsaraService()
logger.info("✅ SamsaraService initialized successfully.")
