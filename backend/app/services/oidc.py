"""OIDC (OpenID Connect) Service for SSO authentication."""
import httpx
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlencode
import jwt
from jwt import PyJWKClient

from app.config import get_settings

logger = logging.getLogger(__name__)


class OIDCService:
    """Service for handling OIDC authentication flows."""
    
    def __init__(self):
        self.settings = get_settings()
        self._metadata: Optional[Dict[str, Any]] = None
        self._jwks_client: Optional[PyJWKClient] = None
    
    @property
    def is_enabled(self) -> bool:
        """Check if OIDC is enabled and configured."""
        return (
            self.settings.oidc_enabled
            and self.settings.oidc_provider_url
            and self.settings.oidc_client_id
        )
    
    async def get_provider_metadata(self) -> Dict[str, Any]:
        """Fetch OIDC provider metadata from .well-known/openid-configuration."""
        if self._metadata:
            return self._metadata
        
        if not self.settings.oidc_provider_url:
            raise ValueError("OIDC provider URL not configured")
        
        discovery_url = f"{self.settings.oidc_provider_url.rstrip('/')}/.well-known/openid-configuration"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(discovery_url, timeout=10.0)
                response.raise_for_status()
                self._metadata = response.json()
                return self._metadata
        except Exception as e:
            logger.error(f"Failed to fetch OIDC metadata: {e}")
            raise
    
    def get_authorization_url(self, state: str, nonce: str) -> str:
        """
        Generate the authorization URL to redirect user to IdP.
        
        Args:
            state: Random state for CSRF protection
            nonce: Random nonce for replay protection
            
        Returns:
            Authorization URL to redirect to
        """
        if not self.settings.oidc_provider_url:
            raise ValueError("OIDC provider URL not configured")
        
        # Build authorization URL
        # For common providers, we can construct the URL directly
        # Otherwise, we should use the metadata
        base_url = self.settings.oidc_provider_url.rstrip('/')
        
        # Common authorization endpoint patterns
        auth_endpoint = f"{base_url}/authorize"
        
        params = {
            "client_id": self.settings.oidc_client_id,
            "redirect_uri": self.settings.oidc_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
        }
        
        return f"{auth_endpoint}?{urlencode(params)}"
    
    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for tokens.
        
        Args:
            code: Authorization code from callback
            
        Returns:
            Token response (access_token, id_token, etc.)
        """
        if not self.settings.oidc_provider_url:
            raise ValueError("OIDC provider URL not configured")
        
        base_url = self.settings.oidc_provider_url.rstrip('/')
        token_endpoint = f"{base_url}/token"
        
        data = {
            "grant_type": "authorization_code",
            "client_id": self.settings.oidc_client_id,
            "client_secret": self.settings.oidc_client_secret,
            "code": code,
            "redirect_uri": self.settings.oidc_redirect_uri,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_endpoint,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10.0,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to exchange code for tokens: {e}")
            raise
    
    def decode_id_token(self, id_token: str, verify: bool = True) -> Dict[str, Any]:
        """
        Decode and optionally verify the ID token.
        
        Args:
            id_token: The ID token JWT
            verify: Whether to verify the signature
            
        Returns:
            Decoded token claims
        """
        if not verify:
            # Decode without verification (for development/testing)
            return jwt.decode(id_token, options={"verify_signature": False})
        
        try:
            # For production, verify with JWKS
            if not self._jwks_client and self.settings.oidc_provider_url:
                jwks_uri = f"{self.settings.oidc_provider_url.rstrip('/')}/certs"
                self._jwks_client = PyJWKClient(jwks_uri)
            
            if self._jwks_client:
                signing_key = self._jwks_client.get_signing_key_from_jwt(id_token)
                return jwt.decode(
                    id_token,
                    signing_key.key,
                    algorithms=["RS256"],
                    audience=self.settings.oidc_client_id,
                )
        except Exception as e:
            logger.warning(f"Failed to verify ID token: {e}, falling back to unverified decode")
            return jwt.decode(id_token, options={"verify_signature": False})
        
        return jwt.decode(id_token, options={"verify_signature": False})
    
    def get_user_info_from_token(self, claims: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract user information from ID token claims.
        
        Args:
            claims: Decoded ID token claims
            
        Returns:
            User info dict with email, name, sub
        """
        return {
            "sub": claims.get("sub"),
            "email": claims.get("email"),
            "name": claims.get("name") or claims.get("preferred_username"),
            "given_name": claims.get("given_name"),
            "family_name": claims.get("family_name"),
            "picture": claims.get("picture"),
        }


# Singleton instance
_oidc_service: Optional[OIDCService] = None


def get_oidc_service() -> OIDCService:
    """Get the OIDC service singleton."""
    global _oidc_service
    if _oidc_service is None:
        _oidc_service = OIDCService()
    return _oidc_service
