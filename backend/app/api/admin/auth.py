"""Authentication API endpoints."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_client_ip, get_request_logger
from app.config import get_settings
from app.core.auth import get_current_active_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from app.database import get_db
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.services.logger import RequestLogger

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Get current user and verify they are a superuser."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    return current_user


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
    logger: RequestLogger = Depends(get_request_logger),
):
    """Login with username/email and password."""
    # Find user by username or email
    result = await db.execute(
        select(User).where(
            (User.username == credentials.username) | (User.email == credentials.username)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User account is disabled")
    
    # Create tokens
    access_token = create_access_token(
        subject=str(user.id),
        additional_claims={"email": user.email, "is_superuser": user.is_superuser},
    )
    refresh_token = create_refresh_token(subject=str(user.id))
    
    # Log login
    await logger.log_audit(
        user=user,
        action="login",
        resource_type="user",
        resource_id=user.id,
        ip_address=get_client_ip(request),
    )
    await db.commit()
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    logger: RequestLogger = Depends(get_request_logger),
):
    """Register a new user account."""
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if username already exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Create user (inactive until admin approves)
    user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        organization_id=user_data.organization_id,
        group_id=user_data.group_id,
        is_active=False,  # Requires admin approval
        is_superuser=False,
        auth_provider="local",
    )
    
    db.add(user)
    await db.flush()
    
    # Log registration
    await logger.log_audit(
        user=user,
        action="register",
        resource_type="user",
        resource_id=user.id,
        ip_address=get_client_ip(request),
    )
    await db.commit()
    await db.refresh(user)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        auth_provider=user.auth_provider,
        organization_id=user.organization_id,
        group_id=user.group_id,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using refresh token."""
    payload = verify_token(refresh_token, expected_type="refresh")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    # Verify user still exists and is active
    from uuid import UUID
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")
    
    # Create new tokens
    access_token = create_access_token(
        subject=str(user.id),
        additional_claims={"email": user.email, "is_superuser": user.is_superuser},
    )
    new_refresh_token = create_refresh_token(subject=str(user.id))
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_active_user),
):
    """Get current authenticated user information."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        auth_provider=current_user.auth_provider,
        organization_id=current_user.organization_id,
        group_id=current_user.group_id,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


# ============================================================================
# Registration Approval Endpoints (Admin only)
# ============================================================================

@router.get("/pending-registrations")
async def get_pending_registrations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Get list of pending registration requests (inactive local users)."""
    result = await db.execute(
        select(User)
        .where(User.is_active == False)
        .where(User.auth_provider == "local")
        .order_by(User.created_at.desc())
    )
    pending_users = result.scalars().all()
    
    return {
        "pending_registrations": [
            {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.isoformat(),
            }
            for user in pending_users
        ],
        "count": len(pending_users),
    }


@router.put("/registrations/{user_id}/approve")
async def approve_registration(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Approve a pending registration and activate the user."""
    from uuid import UUID
    
    result = await db.execute(
        select(User).where(User.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_active:
        raise HTTPException(status_code=400, detail="User is already active")
    
    user.is_active = True
    await db.commit()
    
    return {
        "message": f"Registration approved for {user.username}",
        "user_id": str(user.id),
    }


@router.post("/admin/create-user")
async def admin_create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Admin creates a new user account (directly active, no approval needed)."""
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if username already exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Create user (directly active since admin is creating)
    user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        organization_id=user_data.organization_id,
        group_id=user_data.group_id,
        is_active=True,  # Directly active - created by admin
        is_superuser=False,
        auth_provider="local",
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return {
        "message": f"User {user.username} created successfully",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
        }
    }

@router.put("/registrations/{user_id}/reject")
async def reject_registration(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Reject a pending registration and delete the user."""
    from uuid import UUID
    from sqlalchemy import delete, text
    
    user_uuid = UUID(user_id)
    
    result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_active:
        raise HTTPException(status_code=400, detail="Cannot reject an active user")
    
    original_username = user.username
    
    # Use raw SQL to delete all FK references - more reliable than ORM
    await db.execute(text("DELETE FROM request_logs WHERE user_id = :uid"), {"uid": user_uuid})
    await db.execute(text("DELETE FROM api_keys WHERE user_id = :uid"), {"uid": user_uuid})
    await db.execute(text("DELETE FROM user_roles WHERE user_id = :uid"), {"uid": user_uuid})
    await db.execute(text("DELETE FROM org_join_requests WHERE user_id = :uid"), {"uid": user_uuid})
    await db.execute(text("DELETE FROM model_access_requests WHERE user_id = :uid"), {"uid": user_uuid})
    await db.execute(text("DELETE FROM user_model_access WHERE user_id = :uid"), {"uid": user_uuid})
    await db.execute(text("DELETE FROM audit_logs WHERE user_id = :uid"), {"uid": user_uuid})
    
    # Delete the user
    await db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_uuid})
    await db.commit()
    
    return {
        "message": f"Registration rejected for {original_username}",
    }


# ============================================================================
# OIDC (OpenID Connect) SSO Endpoints
# ============================================================================

import secrets
from fastapi.responses import RedirectResponse
from app.services.oidc import get_oidc_service


@router.get("/oidc/config")
async def get_oidc_config():
    """Get OIDC configuration status (enabled/disabled)."""
    oidc_service = get_oidc_service()
    return {
        "oidc_enabled": oidc_service.is_enabled,
        "provider_url": settings.oidc_provider_url if oidc_service.is_enabled else None,
    }


@router.get("/oidc/login")
async def oidc_login():
    """Start OIDC login flow. Redirects to IdP authorization page."""
    oidc_service = get_oidc_service()
    
    if not oidc_service.is_enabled:
        raise HTTPException(status_code=400, detail="OIDC is not enabled")
    
    # Generate state and nonce for security
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    
    # In production, store state/nonce in session or cache for validation
    # For simplicity, we'll include them in the flow
    
    auth_url = oidc_service.get_authorization_url(state=state, nonce=nonce)
    
    return RedirectResponse(url=auth_url)


@router.get("/oidc/callback")
async def oidc_callback(
    code: str,
    state: str = None,
    error: str = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    logger: RequestLogger = Depends(get_request_logger),
):
    """Handle OIDC callback from IdP."""
    if error:
        # Redirect to login page with error
        return RedirectResponse(url=f"/login?error={error}")
    
    oidc_service = get_oidc_service()
    
    if not oidc_service.is_enabled:
        raise HTTPException(status_code=400, detail="OIDC is not enabled")
    
    try:
        # Exchange code for tokens
        tokens = await oidc_service.exchange_code_for_tokens(code)
        
        id_token = tokens.get("id_token")
        if not id_token:
            raise HTTPException(status_code=400, detail="No ID token received")
        
        # Decode and extract user info
        claims = oidc_service.decode_id_token(id_token, verify=False)  # Set verify=True in production
        user_info = oidc_service.get_user_info_from_token(claims)
        
        email = user_info.get("email")
        sub = user_info.get("sub")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by IdP")
        
        # Find or create user
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if not user:
            # Create new user for OIDC authentication
            username = email.split("@")[0]
            # Ensure unique username
            base_username = username
            counter = 1
            while True:
                result = await db.execute(select(User).where(User.username == username))
                if not result.scalar_one_or_none():
                    break
                username = f"{base_username}{counter}"
                counter += 1
            
            user = User(
                email=email,
                username=username,
                password_hash=None,  # No password for OIDC users
                is_active=True,
                is_superuser=False,
                auth_provider="oidc",
                external_id=sub,
            )
            db.add(user)
            await db.flush()
            
            # Log registration
            await logger.log_audit(
                user=user,
                action="oidc_register",
                resource_type="user",
                resource_id=user.id,
                ip_address=get_client_ip(request) if request else None,
            )
        else:
            # Update external_id if not set
            if not user.external_id and sub:
                user.external_id = sub
                user.auth_provider = "oidc"
            
            # Log login
            await logger.log_audit(
                user=user,
                action="oidc_login",
                resource_type="user",
                resource_id=user.id,
                ip_address=get_client_ip(request) if request else None,
            )
        
        if not user.is_active:
            return RedirectResponse(url="/login?error=account_disabled")
        
        await db.commit()
        
        # Create JWT tokens
        access_token = create_access_token(
            subject=str(user.id),
            additional_claims={"email": user.email, "is_superuser": user.is_superuser},
        )
        refresh_token = create_refresh_token(subject=str(user.id))
        
        # Redirect to frontend with tokens
        # In production, use HTTP-only cookies or a more secure method
        redirect_url = f"/login?access_token={access_token}&refresh_token={refresh_token}"
        
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        import logging
        logging.error(f"OIDC callback error: {e}")
        return RedirectResponse(url=f"/login?error=oidc_failed")


# ============================================================================
# Multi-Provider SSO (Google, Keycloak)
# ============================================================================

from urllib.parse import urlencode


@router.get("/sso/providers")
async def get_sso_providers():
    """Get list of enabled SSO providers."""
    providers = []
    
    # Legacy generic OIDC
    if settings.oidc_enabled and settings.oidc_provider_url:
        providers.append({
            "id": "oidc",
            "name": "SSO",
            "icon": "🔐",
            "enabled": True,
        })
    
    # Google OAuth2
    if settings.google_oauth_enabled and settings.google_client_id:
        providers.append({
            "id": "google",
            "name": "Google",
            "icon": "🔵",
            "enabled": True,
        })
    
    # Keycloak
    if settings.keycloak_enabled and settings.keycloak_server_url:
        providers.append({
            "id": "keycloak",
            "name": "Keycloak",
            "icon": "🔴",
            "enabled": True,
        })
    
    return {
        "providers": providers,
        "any_enabled": len(providers) > 0,
    }


@router.get("/google/login")
async def google_login():
    """Start Google OAuth2 login flow."""
    if not settings.google_oauth_enabled or not settings.google_client_id:
        raise HTTPException(status_code=400, detail="Google OAuth is not enabled")
    
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri or f"{settings.api_base_url}/api/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "access_type": "offline",
        "prompt": "consent",
    }
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str = None,
    error: str = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    logger: RequestLogger = Depends(get_request_logger),
):
    """Handle Google OAuth2 callback."""
    if error:
        return RedirectResponse(url=f"/login?error={error}")
    
    if not code:
        return RedirectResponse(url="/login?error=no_code")
    
    try:
        import httpx
        
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.google_redirect_uri or f"{settings.api_base_url}/api/auth/google/callback",
                },
            )
            
            if response.status_code != 200:
                return RedirectResponse(url="/login?error=token_exchange_failed")
            
            tokens = response.json()
        
        # Decode ID token
        id_token = tokens.get("id_token")
        if not id_token:
            return RedirectResponse(url="/login?error=no_id_token")
        
        import jwt
        claims = jwt.decode(id_token, options={"verify_signature": False})
        
        email = claims.get("email")
        sub = claims.get("sub")
        
        if not email:
            return RedirectResponse(url="/login?error=no_email")
        
        # Find or create user (same logic as generic OIDC)
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if not user:
            username = email.split("@")[0]
            base_username = username
            counter = 1
            while True:
                result = await db.execute(select(User).where(User.username == username))
                if not result.scalar_one_or_none():
                    break
                username = f"{base_username}{counter}"
                counter += 1
            
            user = User(
                email=email,
                username=username,
                password_hash=None,
                is_active=True,
                is_superuser=False,
                auth_provider="google",
                external_id=sub,
            )
            db.add(user)
            await db.flush()
        else:
            if not user.external_id and sub:
                user.external_id = sub
                user.auth_provider = "google"
        
        if not user.is_active:
            return RedirectResponse(url="/login?error=account_disabled")
        
        await db.commit()
        
        access_token = create_access_token(
            subject=str(user.id),
            additional_claims={"email": user.email, "is_superuser": user.is_superuser},
        )
        refresh_token = create_refresh_token(subject=str(user.id))
        
        return RedirectResponse(url=f"/login?access_token={access_token}&refresh_token={refresh_token}")
        
    except Exception as e:
        import logging
        logging.error(f"Google callback error: {e}")
        return RedirectResponse(url="/login?error=google_failed")


@router.get("/keycloak/login")
async def keycloak_login():
    """Start Keycloak OIDC login flow."""
    if not settings.keycloak_enabled or not settings.keycloak_server_url:
        raise HTTPException(status_code=400, detail="Keycloak is not enabled")
    
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    
    base_url = settings.keycloak_server_url.rstrip('/')
    realm = settings.keycloak_realm or "master"
    
    params = {
        "client_id": settings.keycloak_client_id,
        "redirect_uri": settings.keycloak_redirect_uri or f"{settings.api_base_url}/api/auth/keycloak/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
    }
    
    auth_url = f"{base_url}/realms/{realm}/protocol/openid-connect/auth?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/keycloak/callback")
async def keycloak_callback(
    code: str = None,
    error: str = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    logger: RequestLogger = Depends(get_request_logger),
):
    """Handle Keycloak OIDC callback."""
    if error:
        return RedirectResponse(url=f"/login?error={error}")
    
    if not code:
        return RedirectResponse(url="/login?error=no_code")
    
    try:
        import httpx
        
        base_url = settings.keycloak_server_url.rstrip('/')
        realm = settings.keycloak_realm or "master"
        token_url = f"{base_url}/realms/{realm}/protocol/openid-connect/token"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "client_id": settings.keycloak_client_id,
                    "client_secret": settings.keycloak_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.keycloak_redirect_uri or f"{settings.api_base_url}/api/auth/keycloak/callback",
                },
            )
            
            if response.status_code != 200:
                return RedirectResponse(url="/login?error=token_exchange_failed")
            
            tokens = response.json()
        
        id_token = tokens.get("id_token")
        if not id_token:
            return RedirectResponse(url="/login?error=no_id_token")
        
        import jwt
        claims = jwt.decode(id_token, options={"verify_signature": False})
        
        email = claims.get("email")
        sub = claims.get("sub")
        
        if not email:
            return RedirectResponse(url="/login?error=no_email")
        
        # Find or create user
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if not user:
            username = email.split("@")[0]
            base_username = username
            counter = 1
            while True:
                result = await db.execute(select(User).where(User.username == username))
                if not result.scalar_one_or_none():
                    break
                username = f"{base_username}{counter}"
                counter += 1
            
            user = User(
                email=email,
                username=username,
                password_hash=None,
                is_active=True,
                is_superuser=False,
                auth_provider="keycloak",
                external_id=sub,
            )
            db.add(user)
            await db.flush()
        else:
            if not user.external_id and sub:
                user.external_id = sub
                user.auth_provider = "keycloak"
        
        if not user.is_active:
            return RedirectResponse(url="/login?error=account_disabled")
        
        await db.commit()
        
        access_token = create_access_token(
            subject=str(user.id),
            additional_claims={"email": user.email, "is_superuser": user.is_superuser},
        )
        refresh_token = create_refresh_token(subject=str(user.id))
        
        return RedirectResponse(url=f"/login?access_token={access_token}&refresh_token={refresh_token}")
        
    except Exception as e:
        import logging
        logging.error(f"Keycloak callback error: {e}")
        return RedirectResponse(url="/login?error=keycloak_failed")
