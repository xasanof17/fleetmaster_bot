"""
Samsara API Service for FleetMaster Bot
Final Production Version: Multi-org, Background Refresh, and full PM_Trucker Compatibility.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any

import aiohttp

from config import settings
from utils.helpers import meters_to_miles, parse_series_value_and_time
from utils.logger import get_logger

logger = get_logger("services.samsara_service")


# =====================================================
# INTERNAL PER-ORG CLIENT
# =====================================================
class _SamsaraOrgClient:
    def __init__(self, api_token: str, org_name: str):
        self.org_name = org_name
        self.base_url = settings.SAMSARA_BASE_URL.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        self.session: aiohttp.ClientSession | None = None
        self._session_lock = asyncio.Lock()

        self._vehicle_cache: list[dict[str, Any]] = []
        self._cache_timestamp: datetime | None = None

    async def open(self):
        async with self._session_lock:
            if not self.session or self.session.closed:
                connector = aiohttp.TCPConnector(limit=20, limit_per_host=10)
                timeout = aiohttp.ClientTimeout(total=30, connect=5, sock_read=15)
                self.session = aiohttp.ClientSession(
                    headers=self.headers, timeout=timeout, connector=connector
                )
                logger.info(f"🔌 Session created for {self.org_name}")

    async def close(self):
        async with self._session_lock:
            if self.session and not self.session.closed:
                await self.session.close()
                logger.info(f"🔒 Session closed for {self.org_name}")
            self.session = None

    async def request(self, endpoint: str, params: dict | None = None):
        if not self.session or self.session.closed:
            await self.open()
        try:
            async with self.session.get(f"{self.base_url}{endpoint}", params=params) as r:
                if r.status == 200:
                    return await r.json()
                logger.error(f"❌ {self.org_name} API Error {r.status}")
                return None
        except Exception as e:
            logger.error(f"💥 {self.org_name} Connection Error: {e}")
            return None

    async def fetch_all_vehicles(self) -> list[dict[str, Any]]:
        vehicles: list[dict[str, Any]] = []
        cursor = None

        while True:
            params = {"types": "light_duty,medium_duty,heavy_duty"}
            if cursor:
                params["after"] = cursor

            data = await self.request("/fleet/vehicles", params)
            if not data or "data" not in data:
                break

            for v in data["data"]:
                v["_org"] = self.org_name
                vehicles.append(v)

            pg = data.get("pagination", {})
            if not pg.get("hasNextPage"):
                break

            cursor = pg.get("endCursor")

        self._vehicle_cache = vehicles
        self._cache_timestamp = datetime.now(timezone.utc)
        return vehicles


# =====================================================
# PUBLIC SERVICE (FACADE)
# =====================================================
class SamsaraService:
    def __init__(self):
        self.orgs: list[_SamsaraOrgClient] = []
        self._init_orgs()

        self._session_refs = 0
        self._session_lock = asyncio.Lock()

        self._running = False
        self._refresh_interval = 3600

        # 🔑 global dedup memory
        self._vehicle_org_hint: dict[str, str] = {}

    def _init_orgs(self):
        tokens = [
            (getattr(settings, "SAMSARA_API_TOKEN", None), "ORG_1"),
            (getattr(settings, "SAMSARA_API_TOKEN_2", None), "ORG_2"),
        ]
        for token, name in tokens:
            if token:
                self.orgs.append(_SamsaraOrgClient(token, name))

    async def __aenter__(self):
        async with self._session_lock:
            if self._session_refs == 0:
                await asyncio.gather(*[org.open() for org in self.orgs])
            self._session_refs += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        async with self._session_lock:
            self._session_refs -= 1
            if self._session_refs <= 0:
                await self.close_all()

    async def close_all(self):
        await asyncio.gather(*[org.close() for org in self.orgs], return_exceptions=True)
        logger.info("🛑 All Samsara sessions closed")

    # =====================================================
    # HELPERS
    # =====================================================
    def _vehicle_key(self, v: dict) -> str:
        return (
            (v.get("vin") or v.get("externalIds", {}).get("samsara.vin"))
            or v.get("name")
            or v.get("licensePlate")
            or ""
        ).lower()

    # =====================================================
    # DATA
    # =====================================================
    async def get_vehicles(self, use_cache: bool = True) -> list[dict]:
        """
        Always returns DEDUPLICATED vehicles across all orgs.
        Dedup key: VIN > NAME > PLATE
        """

        vehicles: list[dict] = []

        if use_cache:
            for org in self.orgs:
                vehicles.extend(org._vehicle_cache)
        else:
            results = await asyncio.gather(*[org.fetch_all_vehicles() for org in self.orgs])
            for sub in results:
                vehicles.extend(sub)

        seen = set()
        unique: list[dict] = []

        for v in vehicles:
            key = self._vehicle_key(v)
            if not key:
                continue
            if key in seen:
                continue

            seen.add(key)
            unique.append(v)
            self._vehicle_org_hint[key] = v["_org"]

        logger.warning(f"[DEDUP CHECK] vehicles before={len(vehicles)} after={len(unique)}")

        return unique

    async def get_vehicle_by_id(self, vehicle_id: str) -> dict | None:
        vehicles = await self.get_vehicles(use_cache=True)
        return next((v for v in vehicles if str(v.get("id")) == str(vehicle_id)), None)

    async def search_vehicles(
        self, query: str, search_by: str = "all", limit: int = 50
    ) -> list[dict]:
        q = query.lower().strip()
        vehicles = await self.get_vehicles(use_cache=True)

        seen = set()
        results = []

        for v in vehicles:
            key = self._vehicle_key(v)
            if not key or key in seen:
                continue

            name = (v.get("name") or "").lower()
            vin = (v.get("vin") or v.get("externalIds", {}).get("samsara.vin", "")).lower()
            plate = (v.get("licensePlate") or "").lower()

            if (
                search_by == "name"
                and q in name
                or search_by == "vin"
                and q in vin
                or search_by == "plate"
                and q in plate
                or search_by == "all"
                and (q in name or q in vin or q in plate)
            ):
                seen.add(key)
                results.append(v)
                self._vehicle_org_hint[key] = v["_org"]

                if len(results) >= limit:
                    break

        return results

    # =====================================================
    # STATS & LOCATION
    # =====================================================
    async def get_vehicle_with_stats(self, vehicle_id: str) -> dict | None:
        vehicle = await self.get_vehicle_by_id(vehicle_id)
        if not vehicle:
            return None

        client = next((o for o in self.orgs if o.org_name == vehicle["_org"]), None)
        if not client:
            return vehicle

        stats = await client.request(
            "/fleet/vehicles/stats/feed",
            {"types": "obdOdometerMeters", "vehicleIds": vehicle_id},
        )

        if stats and stats.get("data"):
            s = stats["data"][0]
            meters, ts = parse_series_value_and_time(s.get("obdOdometerMeters"))
            vehicle["odometer"] = meters_to_miles(meters) if meters else None
            vehicle["lastUpdated"] = ts

        return vehicle

    async def get_vehicle_location(self, vehicle_id: str) -> dict | None:
        vehicle = await self.get_vehicle_by_id(vehicle_id)
        if not vehicle:
            return None

        client = next((o for o in self.orgs if o.org_name == vehicle["_org"]), None)
        if not client:
            return None

        result = await client.request(
            "/fleet/vehicles/stats/feed",
            {"types": "gps", "vehicleIds": vehicle_id},
        )

        if result and result.get("data"):
            gps = result["data"][0].get("gps")
            if gps:
                last = gps[-1]
                return {
                    "latitude": last.get("latitude"),
                    "longitude": last.get("longitude"),
                    "address": last.get("reverseGeo", {}).get("formattedLocation"),
                    "time": last.get("time") or last.get("timestamp"),
                }

        return None

    async def test_connection(self) -> bool:
        """
        Compatibility method (old code expects it).
        Returns True only if ALL orgs respond.
        """
        if not self.orgs:
            logger.error("❌ No Samsara org tokens configured")
            return False

        try:
            async with self:
                results = await asyncio.gather(
                    *[org.request("/fleet/vehicles", {"limit": 1}) for org in self.orgs],
                    return_exceptions=True,
                )

            ok = True
            for org, r in zip(self.orgs, results, strict=False):
                if isinstance(r, Exception) or r is None:
                    logger.error(f"❌ Samsara connection FAILED [{org.org_name}]")
                    ok = False
                else:
                    logger.info(f"✅ Samsara connection OK [{org.org_name}]")

            return ok
        except Exception as e:
            logger.error(f"❌ Samsara test_connection crashed: {e}")
            return False

    # =====================================================
    # BACKGROUND LOOP
    # =====================================================
    async def run_forever(self):
        if self._running:
            return

        self._running = True
        logger.info("🔄 Samsara Background Loop Started")

        try:
            async with self:
                while self._running:
                    try:
                        await self.get_vehicles(use_cache=False)
                        logger.info("✅ Cache refreshed")
                    except Exception as e:
                        logger.error(f"💥 Refresh Error: {e}")
                    await asyncio.sleep(self._refresh_interval)
        finally:
            self._running = False


# =====================================================
# SINGLETON
# =====================================================
samsara_service = SamsaraService()
