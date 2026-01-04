"""Security Scan Admin API endpoints."""
import httpx
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_superuser
from app.database import get_db
from app.models.user import User
from app.models.llm_model import LLMModel, ModelEndpoint
from app.models.provider import Provider
from app.models.security_scan import (
    SecurityScanResult, SecurityScanProfile, SecurityVulnerability,
    ScanStatus, ScanType, VulnerabilitySeverity
)
from app.services.security_scan import get_security_scan_service

router = APIRouter(prefix="/security", tags=["Security Scan"])

# Store running background tasks to prevent garbage collection
_running_scan_tasks = set()


# ============================================================================
# Schemas
# ============================================================================

class ScanRequest(BaseModel):
    scan_type: str = Field(default="quick", description="quick, standard, or comprehensive")
    categories: Optional[List[str]] = Field(default=None, description="Categories to test")


class VulnerabilityResponse(BaseModel):
    category: str
    probe_name: str
    severity: str
    probe_input: Optional[str]
    model_output: Optional[str]
    detection_reason: Optional[str]
    recommendation: Optional[str]


class ScanResultResponse(BaseModel):
    id: UUID
    model_alias: str
    scan_type: str
    status: str
    security_score: Optional[int]
    total_probes: int
    passed_probes: int
    failed_probes: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    vulnerabilities: List[VulnerabilityResponse] = []
    detailed_results: Optional[dict] = None  # Full scan results including categories_tested


class ScanSummaryResponse(BaseModel):
    id: UUID
    model_alias: str
    scan_type: str
    status: str
    security_score: Optional[int]
    total_vulnerabilities: int
    created_at: datetime


# ============================================================================
# Helper Functions
# ============================================================================

async def call_model_api(
    provider: Provider,
    endpoint: ModelEndpoint,
    prompt: str,
) -> str:
    """Call the LLM API with a prompt and return the response."""
    try:
        base_url = provider.api_base_url.rstrip("/")
        model_name = endpoint.provider_model_name
        
        # Build request based on provider type
        if provider.provider_type in ["openai", "openai_compatible"]:
            url = f"{base_url}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            if provider.api_key:
                headers["Authorization"] = f"Bearer {provider.api_key}"
            
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
            }
        elif provider.provider_type == "ollama":
            url = f"{base_url}/api/generate"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
            }
        else:
            # Generic OpenAI-compatible format
            url = f"{base_url}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            if provider.api_key:
                headers["Authorization"] = f"Bearer {provider.api_key}"
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
            }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        # Extract response text based on format
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0].get("message", {}).get("content", "")
        elif "response" in data:
            return data["response"]
        else:
            return str(data)
            
    except Exception as e:
        raise Exception(f"Model API call failed: {str(e)}")


async def call_model_api_primitive(
    provider_type: str,
    api_base: str,
    api_key: Optional[str],
    model_name: str,
    prompt: str,
) -> str:
    """Call model API using primitive values (for background tasks)."""
    try:
        base_url = api_base.rstrip("/") if api_base else "http://localhost:11434"
        
        if provider_type == "ollama":
            url = f"{base_url}/api/generate"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
            }
        else:
            url = f"{base_url}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
            }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0].get("message", {}).get("content", "")
        elif "response" in data:
            return data["response"]
        else:
            return str(data)
            
    except Exception as e:
        raise Exception(f"Model API call failed: {str(e)}")


async def run_scan_background(
    scan_id: UUID,
    model_alias: str,
    model_id: UUID,
    provider_type: str,
    provider_api_base: str,
    provider_api_key: Optional[str],
    endpoint_model_name: str,
    scan_type: str,
    categories: Optional[List[str]],
    db_url: str,
):
    """Background task to run the security scan."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[SCAN] Background task started for scan_id={scan_id}")
    print(f"[SCAN] Background task started for scan_id={scan_id}", flush=True)
    
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    # Ensure we use asyncpg driver for async operations
    async_db_url = db_url
    if "postgresql://" in db_url and "+asyncpg" not in db_url:
        async_db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    elif "postgresql+psycopg2" in db_url:
        async_db_url = db_url.replace("postgresql+psycopg2", "postgresql+asyncpg")
    
    try:
        engine = create_async_engine(async_db_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session() as db:
            try:
                # Get scan result record
                result = await db.execute(select(SecurityScanResult).where(SecurityScanResult.id == scan_id))
                scan_result = result.scalar_one_or_none()
                
                if not scan_result:
                    logger.error(f"[SCAN] Scan result not found for id={scan_id}")
                    return
                
                # Update status to running
                logger.info(f"[SCAN] Updating status to RUNNING for scan_id={scan_id}")
                scan_result.status = ScanStatus.RUNNING
                scan_result.started_at = datetime.utcnow()
                await db.commit()
                
                # Create model call function using primitives
                async def call_model_fn(prompt: str) -> str:
                    return await call_model_api_primitive(
                        provider_type, provider_api_base, provider_api_key,
                        endpoint_model_name, prompt
                    )
                
                # Run the scan
                service = get_security_scan_service()
                
                if scan_type == "quick":
                    results = await service.run_quick_scan(
                        model_alias, model_id, call_model_fn, categories
                    )
                else:
                    results = await service.run_standard_scan(
                        model_alias, model_id, call_model_fn, categories
                    )
                
                # Update scan result
                logger.info(f"[SCAN] Scan completed for scan_id={scan_id}")
                scan_result.status = ScanStatus.COMPLETED
                scan_result.completed_at = datetime.utcnow()
                scan_result.total_probes = results["summary"]["total_probes"]
                scan_result.passed_probes = results["summary"]["passed"]
                scan_result.failed_probes = results["summary"]["failed"]
                scan_result.security_score = results["security_score"]
                scan_result.detailed_results = results
                
                # Count by severity
                by_severity = results["summary"].get("by_severity", {})
                scan_result.critical_count = by_severity.get("critical", 0)
                scan_result.high_count = by_severity.get("high", 0)
                scan_result.medium_count = by_severity.get("medium", 0)
                scan_result.low_count = by_severity.get("low", 0)
                
                # Create vulnerability records
                for vuln_data in results.get("vulnerabilities", []):
                    vuln = SecurityVulnerability(
                        scan_result_id=scan_id,
                        category=vuln_data["category"],
                        probe_name=vuln_data["probe_name"],
                        severity=VulnerabilitySeverity(vuln_data["severity"]),
                        probe_input=vuln_data.get("probe_input"),
                        model_output=vuln_data.get("model_output"),
                        detection_reason=vuln_data.get("detection_reason"),
                        recommendation=vuln_data.get("recommendation"),
                    )
                    db.add(vuln)
                
                await db.commit()
                logger.info(f"[SCAN] Results saved for scan_id={scan_id}")
                
            except Exception as e:
                logger.error(f"[SCAN] Scan failed with error: {e}")
                scan_result.status = ScanStatus.FAILED
                scan_result.error_message = str(e)
                scan_result.completed_at = datetime.utcnow()
                await db.commit()
            
            finally:
                await engine.dispose()
                
    except Exception as outer_error:
        logger.error(f"[SCAN] Background task failed with outer error: {outer_error}")
        import traceback
        logger.error(traceback.format_exc())


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/models", response_model=List[dict])
async def list_scannable_models(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """List all models that can be scanned (have at least one active endpoint)."""
    result = await db.execute(
        select(LLMModel)
        .where(LLMModel.is_active == True)
        .order_by(LLMModel.alias)
    )
    models = result.scalars().all()
    
    scannable = []
    for model in models:
        # Check if model has active endpoints
        endpoint_result = await db.execute(
            select(ModelEndpoint)
            .where(ModelEndpoint.model_id == model.id)
            .where(ModelEndpoint.is_active == True)
            .limit(1)
        )
        if endpoint_result.scalar_one_or_none():
            scannable.append({
                "id": str(model.id),
                "alias": model.alias,
                "display_name": model.display_name,
                "model_type": model.model_type,
            })
    
    return scannable


@router.post("/scan/{model_id}")
async def start_security_scan(
    model_id: UUID,
    request: ScanRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Start a security scan for a model."""
    print(f"[SCAN-API] start_security_scan called for model_id={model_id}", flush=True)
    # Get model
    result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Get active endpoint
    endpoint_result = await db.execute(
        select(ModelEndpoint)
        .where(ModelEndpoint.model_id == model_id)
        .where(ModelEndpoint.is_active == True)
        .order_by(ModelEndpoint.priority.desc())
        .limit(1)
    )
    endpoint = endpoint_result.scalar_one_or_none()
    
    if not endpoint:
        raise HTTPException(status_code=400, detail="Model has no active endpoints")
    
    # Get provider
    provider_result = await db.execute(
        select(Provider).where(Provider.id == endpoint.provider_id)
    )
    provider = provider_result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=400, detail="Provider not found")
    
    # Create scan result record
    scan_type_enum = ScanType.QUICK if request.scan_type == "quick" else ScanType.STANDARD
    
    scan_result = SecurityScanResult(
        model_id=model.id,
        model_alias=model.alias,
        scan_type=scan_type_enum,
        status=ScanStatus.PENDING,
    )
    db.add(scan_result)
    await db.commit()
    await db.refresh(scan_result)
    
    # Get database URL for background task
    from app.config import get_settings
    settings = get_settings()
    db_url = settings.database_url
    
    # Use asyncio.create_task for async background execution
    import asyncio
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[SCAN] Creating background task for scan_id={scan_result.id}")
    print(f"[SCAN] Creating background task for scan_id={scan_result.id}", flush=True)
    
    task = asyncio.create_task(run_scan_background(
        scan_result.id,
        model.alias,
        model.id,
        provider.provider_type,
        provider.base_url,
        provider.auth_credentials_encrypted,
        endpoint.provider_model_name,
        request.scan_type,
        request.categories,
        db_url,
    ))
    
    # Store task reference to prevent garbage collection
    _running_scan_tasks.add(task)
    task.add_done_callback(lambda t: _running_scan_tasks.discard(t))
    
    logger.info(f"[SCAN] Background task created and stored: {task}")
    print(f"[SCAN] Background task created and stored: {task}", flush=True)
    
    return {
        "scan_id": str(scan_result.id),
        "status": "pending",
        "message": f"Security scan started for model '{model.alias}'",
    }


@router.get("/scan/{scan_id}", response_model=ScanResultResponse)
async def get_scan_result(
    scan_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed scan result."""
    result = await db.execute(
        select(SecurityScanResult).where(SecurityScanResult.id == scan_id)
    )
    scan = result.scalar_one_or_none()
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan result not found")
    
    # Get vulnerabilities
    vuln_result = await db.execute(
        select(SecurityVulnerability)
        .where(SecurityVulnerability.scan_result_id == scan_id)
        .order_by(SecurityVulnerability.created_at)
    )
    vulnerabilities = vuln_result.scalars().all()
    
    return ScanResultResponse(
        id=scan.id,
        model_alias=scan.model_alias,
        scan_type=scan.scan_type.value,
        status=scan.status.value,
        security_score=scan.security_score,
        total_probes=scan.total_probes,
        passed_probes=scan.passed_probes,
        failed_probes=scan.failed_probes,
        critical_count=scan.critical_count,
        high_count=scan.high_count,
        medium_count=scan.medium_count,
        low_count=scan.low_count,
        started_at=scan.started_at,
        completed_at=scan.completed_at,
        error_message=scan.error_message,
        vulnerabilities=[
            VulnerabilityResponse(
                category=v.category,
                probe_name=v.probe_name,
                severity=v.severity.value,
                probe_input=v.probe_input,
                model_output=v.model_output,
                detection_reason=v.detection_reason,
                recommendation=v.recommendation,
            )
            for v in vulnerabilities
        ],
        detailed_results=scan.detailed_results,
    )


from fastapi.responses import JSONResponse
import json as json_module


@router.get("/scan/{scan_id}/download")
async def download_scan_result(
    scan_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Download scan result as JSON file."""
    # Get scan result
    result = await db.execute(select(SecurityScanResult).where(SecurityScanResult.id == scan_id))
    scan = result.scalar_one_or_none()
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan result not found")
    
    # Get vulnerabilities
    vuln_result = await db.execute(
        select(SecurityVulnerability)
        .where(SecurityVulnerability.scan_result_id == scan_id)
        .order_by(SecurityVulnerability.created_at)
    )
    vulnerabilities = vuln_result.scalars().all()
    
    # Build download data
    download_data = {
        "scan_id": str(scan.id),
        "model_alias": scan.model_alias,
        "scan_type": scan.scan_type.value,
        "status": scan.status.value,
        "security_score": scan.security_score,
        "summary": {
            "total_probes": scan.total_probes,
            "passed_probes": scan.passed_probes,
            "failed_probes": scan.failed_probes,
            "critical_count": scan.critical_count,
            "high_count": scan.high_count,
            "medium_count": scan.medium_count,
            "low_count": scan.low_count,
        },
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "error_message": scan.error_message,
        "vulnerabilities": [
            {
                "category": v.category,
                "probe_name": v.probe_name,
                "severity": v.severity.value,
                "probe_input": v.probe_input,
                "model_output": v.model_output,
                "detection_reason": v.detection_reason,
                "recommendation": v.recommendation,
            }
            for v in vulnerabilities
        ],
        "detailed_results": scan.detailed_results,
        "generated_at": datetime.utcnow().isoformat(),
    }
    
    filename = f"security_scan_{scan.model_alias}_{scan.created_at.strftime('%Y%m%d_%H%M%S')}.json"
    
    return JSONResponse(
        content=download_data,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/json",
        }
    )


@router.get("/results", response_model=List[ScanSummaryResponse])
async def list_scan_results(
    model_id: Optional[UUID] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """List recent scan results."""
    query = select(SecurityScanResult).order_by(desc(SecurityScanResult.created_at)).limit(limit)
    
    if model_id:
        query = query.where(SecurityScanResult.model_id == model_id)
    
    result = await db.execute(query)
    scans = result.scalars().all()
    
    return [
        ScanSummaryResponse(
            id=scan.id,
            model_alias=scan.model_alias,
            scan_type=scan.scan_type.value,
            status=scan.status.value,
            security_score=scan.security_score,
            total_vulnerabilities=scan.failed_probes,
            created_at=scan.created_at,
        )
        for scan in scans
    ]


@router.get("/categories")
async def list_scan_categories(
    current_user: User = Depends(get_current_superuser),
):
    """List available security scan categories."""
    service = get_security_scan_service()
    
    categories = []
    for key, data in service.probes.items():
        categories.append({
            "id": key,
            "name": data["name"],
            "description": data["description"],
            "severity": data["severity"],
            "probe_count": len(data["probes"]),
        })
    
    return categories


# ============================================================================
# Garak Integration Endpoints
# ============================================================================

from app.services.garak_service import get_garak_client


@router.get("/garak/status")
async def get_garak_status(
    current_user: User = Depends(get_current_superuser),
):
    """Get Garak installation status and version."""
    client = get_garak_client()
    return await client.get_status()


@router.get("/garak/categories")
async def list_garak_categories(
    current_user: User = Depends(get_current_superuser),
):
    """List available Garak scan categories."""
    client = get_garak_client()
    try:
        return await client.get_categories()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/garak/probes")
async def list_garak_probes(
    current_user: User = Depends(get_current_superuser),
):
    """List all available Garak probes."""
    client = get_garak_client()
    try:
        return await client.get_probes()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


class GarakScanRequest(BaseModel):
    scan_type: str = Field(default="quick", description="quick, standard, or comprehensive")
    categories: Optional[List[str]] = Field(default=None, description="Categories to test")


@router.post("/garak/scan/{model_id}")
async def start_garak_scan(
    model_id: UUID,
    request: GarakScanRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Start a Garak security scan for a model."""
    client = get_garak_client()
    status = await client.get_status()
    
    if not status.get("available"):
        raise HTTPException(status_code=503, detail="Garak service is not available. Please start the Garak container.")
    
    # Get model
    result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Get active endpoint
    endpoint_result = await db.execute(
        select(ModelEndpoint)
        .where(ModelEndpoint.model_id == model_id)
        .where(ModelEndpoint.is_active == True)
        .order_by(ModelEndpoint.priority.desc())
        .limit(1)
    )
    endpoint = endpoint_result.scalar_one_or_none()
    
    if not endpoint:
        raise HTTPException(status_code=400, detail="Model has no active endpoints")
    
    # Get provider
    provider_result = await db.execute(
        select(Provider).where(Provider.id == endpoint.provider_id)
    )
    provider = provider_result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=400, detail="Provider not found")
    
    # Create scan result record
    scan_type_enum = ScanType.QUICK if request.scan_type == "quick" else ScanType.STANDARD
    
    scan_result = SecurityScanResult(
        model_id=model.id,
        model_alias=model.alias,
        scan_type=scan_type_enum,
        status=ScanStatus.PENDING,
    )
    db.add(scan_result)
    await db.commit()
    await db.refresh(scan_result)
    
    # Get database URL for background task
    from app.config import get_settings
    settings = get_settings()
    db_url = settings.database_url
    
    # Start background Garak scan
    background_tasks.add_task(
        run_garak_scan_background,
        scan_result.id,
        model.alias,
        provider.provider_type,
        provider.api_base_url,
        provider.api_key,
        endpoint.provider_model_name,
        request.categories,
        request.scan_type,
        db_url,
    )
    
    return {
        "scan_id": str(scan_result.id),
        "status": "pending",
        "message": f"Garak security scan started for model '{model.alias}'",
        "garak_version": status.get("version"),
    }


async def run_garak_scan_background(
    scan_id: UUID,
    model_alias: str,
    provider_type: str,
    api_base: str,
    api_key: Optional[str],
    model_name: str,
    categories: Optional[List[str]],
    scan_type: str,
    db_url: str,
):
    """Background task to run the Garak security scan."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        try:
            # Get scan result record
            result = await db.execute(select(SecurityScanResult).where(SecurityScanResult.id == scan_id))
            scan_result = result.scalar_one_or_none()
            
            if not scan_result:
                return
            
            # Update status to running
            scan_result.status = ScanStatus.RUNNING
            scan_result.started_at = datetime.utcnow()
            await db.commit()
            
            # Run Garak scan
            garak = get_garak_service()
            results = await garak.run_scan(
                model_name=model_name,
                generator_type=provider_type,
                api_base=api_base,
                api_key=api_key,
                categories=categories,
                scan_type=scan_type,
            )
            
            # Update scan result
            if results.get("status") == "completed":
                scan_result.status = ScanStatus.COMPLETED
            else:
                scan_result.status = ScanStatus.FAILED
                scan_result.error_message = results.get("error", "Unknown error")
            
            scan_result.completed_at = datetime.utcnow()
            scan_result.total_probes = results.get("summary", {}).get("total_probes", 0)
            scan_result.passed_probes = results.get("summary", {}).get("passed", 0)
            scan_result.failed_probes = results.get("summary", {}).get("failed", 0)
            scan_result.security_score = garak.calculate_security_score(results.get("summary", {}))
            scan_result.detailed_results = results
            
            # Count by severity
            by_severity = results.get("summary", {}).get("by_severity", {})
            scan_result.critical_count = by_severity.get("critical", 0)
            scan_result.high_count = by_severity.get("high", 0)
            scan_result.medium_count = by_severity.get("medium", 0)
            scan_result.low_count = by_severity.get("low", 0)
            
            # Create vulnerability records
            for vuln_data in results.get("vulnerabilities", []):
                vuln = SecurityVulnerability(
                    scan_result_id=scan_id,
                    category=vuln_data["category"],
                    probe_name=vuln_data["probe_name"],
                    severity=VulnerabilitySeverity(vuln_data["severity"]),
                    detection_reason=f"Failed {vuln_data.get('failed_count', 0)} out of {vuln_data.get('total_count', 0)} tests",
                )
                db.add(vuln)
            
            await db.commit()
            
        except Exception as e:
            scan_result.status = ScanStatus.FAILED
            scan_result.error_message = str(e)
            scan_result.completed_at = datetime.utcnow()
            await db.commit()
        
        finally:
            await engine.dispose()
