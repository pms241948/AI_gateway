"""Garak LLM Security Scanner Client.

This module provides a client for the Garak security scanner service.
Garak runs as a separate Docker container and is accessed via HTTP.
"""
import os
import logging
from typing import Dict, List, Any, Optional

import httpx

logger = logging.getLogger(__name__)


class GarakClient:
    """Client for communicating with the Garak security scanner service."""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.environ.get("GARAK_SERVICE_URL", "http://garak:8080")
        self._status_cache = None
    
    async def _request(self, method: str, path: str, **kwargs) -> Dict:
        """Make HTTP request to Garak service."""
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError:
            logger.warning(f"Cannot connect to Garak service at {self.base_url}")
            raise RuntimeError("Garak service is not available")
        except httpx.HTTPStatusError as e:
            logger.error(f"Garak service error: {e}")
            raise RuntimeError(f"Garak service error: {e.response.status_code}")
    
    async def check_health(self) -> bool:
        """Check if Garak service is healthy."""
        try:
            result = await self._request("GET", "/health")
            return result.get("status") == "healthy"
        except Exception:
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """Get Garak service status and version."""
        try:
            health = await self.check_health()
            if not health:
                return {"available": False, "version": None, "message": "Garak service is not running"}
            
            version_info = await self._request("GET", "/version")
            return {
                "available": version_info.get("available", False),
                "version": version_info.get("version"),
                "message": "Garak is ready for scanning" if version_info.get("available") else "Garak is not installed",
            }
        except Exception as e:
            return {"available": False, "version": None, "message": str(e)}
    
    async def get_categories(self) -> List[Dict]:
        """Get available scan categories."""
        return await self._request("GET", "/categories")
    
    async def get_probes(self) -> List[Dict]:
        """Get all available probes."""
        return await self._request("GET", "/probes")
    
    async def start_scan(
        self,
        model_name: str,
        generator_type: str,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        categories: Optional[List[str]] = None,
        scan_type: str = "quick",
    ) -> Dict[str, Any]:
        """Start a new security scan."""
        payload = {
            "model_name": model_name,
            "generator_type": generator_type,
            "api_base": api_base,
            "api_key": api_key,
            "categories": categories,
            "scan_type": scan_type,
        }
        return await self._request("POST", "/scan", json=payload)
    
    async def get_scan_result(self, scan_id: str) -> Dict[str, Any]:
        """Get scan result by ID."""
        return await self._request("GET", f"/scan/{scan_id}")


# Legacy compatibility - wrapper for existing code
class GarakService:
    """Wrapper for backward compatibility with existing garak_service usage."""
    
    def __init__(self):
        self._client = GarakClient()
        self._status = None
    
    @property
    def garak_available(self) -> bool:
        """Check if Garak is available (cached)."""
        return self._status.get("available", False) if self._status else False
    
    @property
    def version(self) -> Optional[str]:
        """Get Garak version (cached)."""
        return self._status.get("version") if self._status else None
    
    async def refresh_status(self) -> Dict:
        """Refresh status from Garak service."""
        self._status = await self._client.get_status()
        return self._status
    
    def get_categories(self) -> List[Dict]:
        """Get categories (synchronous, returns empty if not available)."""
        # For backward compatibility - use async version when possible
        return []
    
    async def run_scan(
        self,
        model_name: str,
        generator_type: str,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        categories: Optional[List[str]] = None,
        scan_type: str = "quick",
    ) -> Dict[str, Any]:
        """Run a security scan."""
        # Start scan
        result = await self._client.start_scan(
            model_name=model_name,
            generator_type=generator_type,
            api_base=api_base,
            api_key=api_key,
            categories=categories,
            scan_type=scan_type,
        )
        return result
    
    def calculate_security_score(self, summary: Dict) -> int:
        """Calculate security score (0-100, higher is more secure)."""
        total = summary.get("total_probes", 0)
        if total == 0:
            return 100
        
        passed = summary.get("passed", 0)
        by_severity = summary.get("by_severity", {})
        
        critical_penalty = by_severity.get("critical", 0) * 20
        high_penalty = by_severity.get("high", 0) * 10
        medium_penalty = by_severity.get("medium", 0) * 5
        low_penalty = by_severity.get("low", 0) * 2
        
        base_score = (passed / total) * 100
        penalty = critical_penalty + high_penalty + medium_penalty + low_penalty
        
        return min(100, max(0, int(base_score - penalty)))


# Singleton instances
_garak_client: Optional[GarakClient] = None
_garak_service: Optional[GarakService] = None


def get_garak_client() -> GarakClient:
    """Get the Garak client singleton."""
    global _garak_client
    if _garak_client is None:
        _garak_client = GarakClient()
    return _garak_client


def get_garak_service() -> GarakService:
    """Get the Garak service singleton (legacy compatibility)."""
    global _garak_service
    if _garak_service is None:
        _garak_service = GarakService()
    return _garak_service
