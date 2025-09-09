"""
Samsara API service for FleetMaster Bot
Centralised API logic and pagination. Uses helpers for parsing.
"""
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from config import settings
from utils.helpers import parse_series_value_and_time, meters_to_miles
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
        self.session: Optional[aiohttp.ClientSession] = None
        self._vehicle_cache: Optional[List[Dict[str, Any]]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=3)

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=20, limit_per_host=10)
        timeout = aiohttp.ClientTimeout(total=10, connect=3, sock_read=5)
        self.session = aiohttp.ClientSession(headers=self.headers, timeout=timeout, connector=connector)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()
            self.session = None

    def _is_cache_valid(self) -> bool:
        if not self._vehicle_cache or not self._cache_timestamp:
            return False
        return datetime.utcnow() - self._cache_timestamp < self._cache_duration

    def _cache_vehicles(self, vehicles: List[Dict[str, Any]]) -> None:
        self._vehicle_cache = vehicles
        self._cache_timestamp = datetime.utcnow()
        logger.info(f"Cached {len(vehicles)} vehicles")

    async def _make_request(self, endpoint: str, method: str = "GET", params: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None, max_retries: int = 2) -> Optional[Dict[str, Any]]:
        if not self.session:
            logger.error("Session not initialized. Use 'async with samsara_service' pattern.")
            return None
        url = f"{self.base_url}{endpoint}"
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Request {method} {url} attempt {attempt+1}")
                async with self.session.request(method, url, params=params, json=json) as resp:
                    logger.info(f"Status {resp.status} for {endpoint}")
                    if resp.status == 200:
                        return await resp.json()
                    if resp.status in (401, 403):
                        logger.error(f"Auth/Permission error ({resp.status})")
                        return None
                    if resp.status == 429:
                        if attempt < max_retries:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        logger.warning("Rate limited; giving up")
                        return None
                    # other errors
                    text = await resp.text()
                    logger.error(f"API error {resp.status}: {text}")
                    return None
            except aiohttp.ClientError as e:
                logger.error(f"Network error: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(1)
                    continue
                return None
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(1)
                    continue
                return None
        return None

    async def get_vehicles(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        if use_cache and self._is_cache_valid() and self._vehicle_cache:
            logger.info("Returning vehicles from cache")
            return self._vehicle_cache

        logger.info("Fetching vehicles with pagination")
        vehicles: List[Dict[str, Any]] = []
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

    async def get_vehicle_by_id(self, vehicle_id: str) -> Optional[Dict[str, Any]]:
        # Try cache first
        if self._is_cache_valid() and self._vehicle_cache:
            for v in self._vehicle_cache:
                if str(v.get("id")) == str(vehicle_id):
                    logger.info("Found vehicle in cache")
                    return v
        # Fetch single
        result = await self._make_request(f"/fleet/vehicles/{vehicle_id}")
        if result and "data" in result:
            return result["data"]
        # fallback to full list
        vehicles = await self.get_vehicles(use_cache=False)
        for v in vehicles:
            if str(v.get("id")) == str(vehicle_id):
                return v
        return None

    async def search_vehicles(self, query: str, search_by: str = "name", limit: int = 50) -> List[Dict[str, Any]]:
        vehicles = await self.get_vehicles(use_cache=True)
        if not vehicles:
            return []
        q = query.lower().strip()
        out = []
        for v in vehicles:
            found = False
            if search_by in ("name", "all"):
                if q in (v.get("name") or "").lower():
                    found = True
            if not found and search_by in ("vin", "all"):
                vin = v.get("vin") or v.get("externalIds", {}).get("samsara.vin", "")
                if q in (vin or "").lower():
                    found = True
            if not found and search_by in ("plate", "all"):
                if q in (v.get("licensePlate") or "").lower():
                    found = True
            if found:
                out.append(v)
                if len(out) >= limit:
                    break
        return out

    async def get_vehicle_odometer_stats(self, vehicle_ids: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        params = {"types": "obdOdometerMeters"}
        if vehicle_ids:
            params["vehicleIds"] = ",".join([str(x) for x in vehicle_ids][:50])
        result = await self._make_request("/fleet/vehicles/stats/feed", params=params)
        data: Dict[str, Dict[str, Any]] = {}
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
            vin = s.get("externalIds", {}).get("samsara.vin") or s.get("vin")
            data[str(vid)] = {"vin": vin, "odometer": miles, "lastUpdated": ts}
        return data

    async def get_vehicle_with_stats(self, vehicle_id: str) -> Optional[Dict[str, Any]]:
        vehicle = await self.get_vehicle_by_id(vehicle_id)
        if not vehicle:
            return None
        try:
            odos = await asyncio.wait_for(self.get_vehicle_odometer_stats([vehicle_id]), timeout=6.0)
            odo = odos.get(str(vehicle_id))
            if odo:
                vehicle["odometer"] = odo.get("odometer")
                vehicle["vin"] = odo.get("vin") or vehicle.get("vin")
                vehicle["lastUpdated"] = odo.get("lastUpdated") or vehicle.get("updatedAt")
        except asyncio.TimeoutError:
            logger.warning("Odometer fetch timed out")
        except Exception as e:
            logger.error(f"Error while getting stats: {e}")
        return vehicle

    def clear_cache(self) -> None:
        self._vehicle_cache = None
        self._cache_timestamp = None
        logger.info("Cleared vehicle cache")

    async def test_connection(self) -> bool:
        r = await self._make_request("/fleet/vehicles", params={"limit": 1})
        ok = r is not None
        if ok:
            logger.info("Samsara connection OK")
        else:
            logger.error("Samsara connection failed")
        return ok

    async def get_vehicle_location(self, vehicle_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest GPS location of a vehicle.
        Returns dict: {"latitude": float, "longitude": float, "time": str, "address": str}
        """
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

            # take the latest GPS entry
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


# module-level instance for convenience
samsara_service = SamsaraService()
