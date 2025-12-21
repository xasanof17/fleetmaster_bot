"""
Samsara API Service for FleetMaster Bot
Final Stable Version — Multi-org, LIVE-only GPS, PM_Trucker compatible
"""

import asyncio
from datetime import datetime, timedelta, timezone
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
                self.session = aiohttp.ClientSession(
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                    connector=aiohttp.TCPConnector(limit=20),
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
        except Exception as e:
            logger.error(f"💥 {self.org_name} request failed: {e}")
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

            pg = data.get("pagination") or {}
            if not pg.get("hasNextPage"):
                break
            cursor = pg.get("endCursor")

        self._vehicle_cache = vehicles
        self._cache_timestamp = datetime.now(timezone.utc)
        return vehicles


# =====================================================
# PUBLIC SERVICE
# =====================================================
class SamsaraService:
    LIVE_WINDOW = timedelta(minutes=15)

    def __init__(self):
        self.orgs: list[_SamsaraOrgClient] = []
        self._init_orgs()

        self._session_refs = 0
        self._session_lock = asyncio.Lock()

    def _init_orgs(self):
        for token, name in [
            (settings.SAMSARA_API_TOKEN, "ORG_1"),
            (settings.SAMSARA_API_TOKEN_2, "ORG_2"),
        ]:
            if token:
                self.orgs.append(_SamsaraOrgClient(token, name))

    async def __aenter__(self):
        async with self._session_lock:
            if self._session_refs == 0:
                await asyncio.gather(*[o.open() for o in self.orgs])
            self._session_refs += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        async with self._session_lock:
            self._session_refs -= 1
            if self._session_refs <= 0:
                await asyncio.gather(*[o.close() for o in self.orgs])

    # =====================================================
    # VEHICLES
    # =====================================================
    def _vehicle_key(self, v: dict) -> str:
        return (
            v.get("vin")
            or v.get("externalIds", {}).get("samsara.vin")
            or v.get("name")
            or v.get("licensePlate")
            or ""
        ).lower()

    async def get_vehicles(self, use_cache: bool = True) -> list[dict]:
        vehicles = []
        if use_cache:
            for o in self.orgs:
                vehicles.extend(o._vehicle_cache)
        else:
            res = await asyncio.gather(*[o.fetch_all_vehicles() for o in self.orgs])
            for r in res:
                vehicles.extend(r)

        seen = set()
        unique = []
        for v in vehicles:
            key = self._vehicle_key(v)
            if key and key not in seen:
                seen.add(key)
                unique.append(v)

        logger.warning(f"[DEDUP CHECK] vehicles before={len(vehicles)} after={len(unique)}")
        return unique

    async def get_vehicle_by_id(self, vehicle_id: str) -> dict | None:
        for v in await self.get_vehicles(use_cache=True):
            if str(v.get("id")) == str(vehicle_id):
                return v
        for v in await self.get_vehicles(use_cache=False):
            if str(v.get("id")) == str(vehicle_id):
                return v
        return None

    async def search_vehicles(self, query: str, search_by: str = "all", limit: int = 50):
        q = query.lower().strip()
        vehicles = await self.get_vehicles(use_cache=False)

        out = []
        seen = set()
        for v in vehicles:
            key = self._vehicle_key(v)
            if key in seen:
                continue

            name = (v.get("name") or "").lower()
            vin = (v.get("vin") or "").lower()
            plate = (v.get("licensePlate") or "").lower()

            if (
                (search_by == "name" and q in name)
                or (search_by == "vin" and q in vin)
                or (search_by == "plate" and q in plate)
                or (search_by == "all" and (q in name or q in vin or q in plate))
            ):
                out.append(v)
                seen.add(key)
                if len(out) >= limit:
                    break

        return out

    # =====================================================
    # GPS — LIVE ONLY
    # =====================================================
    async def _try_org(self, org: _SamsaraOrgClient, vin: str):
        vehicles = org._vehicle_cache or await org.fetch_all_vehicles()

        match = next(
            (
                v
                for v in vehicles
                if (v.get("vin") or v.get("externalIds", {}).get("samsara.vin")) == vin
            ),
            None,
        )
        if not match:
            return None

        res = await org.request(
            "/fleet/vehicles/stats/feed",
            {"types": "gps", "vehicleIds": str(match["id"])},
        )

        if not res or not res.get("data"):
            return None

        newest = None
        for d in res["data"]:
            for g in d.get("gps") or []:
                ts_raw = g.get("time") or g.get("timestamp")
                if not ts_raw:
                    continue
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - ts <= self.LIVE_WINDOW and (
                    not newest or ts > newest[0]
                ):
                    newest = (ts, g)

        return newest

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
        now = datetime.now(timezone.utc)

        # -------------------------------------------
        # STEP 1: resolve VIN from ANY org
        # -------------------------------------------
        vehicles = await self.get_vehicles(use_cache=False)
        vehicle = next((v for v in vehicles if str(v.get("id")) == str(vehicle_id)), None)

        if not vehicle:
            logger.warning(f"[GPS] vehicle not found id={vehicle_id}")
            return None

        vin = vehicle.get("vin") or vehicle.get("externalIds", {}).get("samsara.vin")
        if not vin:
            logger.warning(f"[GPS] no VIN id={vehicle_id}")
            return None

        best: tuple[datetime, dict, str] | None = None
        # (timestamp, gps, org_name)

        # -------------------------------------------
        # STEP 2: check ALL orgs
        # -------------------------------------------
        for org in self.orgs:
            # find vehicle in this org by VIN (CACHE FIRST)
            org_vehicle = next(
                (
                    v
                    for v in org._vehicle_cache
                    if (v.get("vin") or v.get("externalIds", {}).get("samsara.vin")) == vin
                ),
                None,
            )

            if not org_vehicle:
                # fallback fetch only if missing
                org_vehicles = await org.fetch_all_vehicles()
                org_vehicle = next(
                    (
                        v
                        for v in org_vehicles
                        if (v.get("vin") or v.get("externalIds", {}).get("samsara.vin")) == vin
                    ),
                    None,
                )

            if not org_vehicle:
                continue

            org_vehicle_id = org_vehicle.get("id")
            if not org_vehicle_id:
                continue

            result = await org.request(
                "/fleet/vehicles/stats/feed",
                {"types": "gps", "vehicleIds": str(org_vehicle_id)},
            )

            if not result or not result.get("data"):
                continue

            for item in result["data"]:
                for g in item.get("gps") or []:
                    ts_raw = g.get("time") or g.get("timestamp")
                    if not ts_raw:
                        continue
                    try:
                        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                    except Exception:
                        continue

                    # -----------------------------------
                    # PICK THE NEWEST GPS ACROSS ALL ORGS
                    # -----------------------------------
                    if not best or ts > best[0]:
                        best = (ts, g, org.org_name)

        if not best:
            logger.warning(f"[NO GPS FOUND] vin={vin}")
            return None

        ts, gps, org_name = best
        confidence = "LIVE" if now - ts <= timedelta(minutes=15) else "STALE"

        logger.warning(f"[GPS SELECTED] org={org_name} ts={ts.isoformat()} confidence={confidence}")

        return {
            "latitude": gps.get("latitude"),
            "longitude": gps.get("longitude"),
            "address": gps.get("reverseGeo", {}).get("formattedLocation"),
            "time": ts,
            "confidence": confidence,
        }

    # =====================================================
    # HEALTH
    # =====================================================
    async def test_connection(self) -> bool:
        try:
            async with self:
                results = await asyncio.gather(
                    *[o.request("/fleet/vehicles", {"limit": 1}) for o in self.orgs],
                    return_exceptions=True,
                )
            return all(r and not isinstance(r, Exception) for r in results)
        except Exception:
            return False


# =====================================================
# SINGLETON
# =====================================================
samsara_service = SamsaraService()
