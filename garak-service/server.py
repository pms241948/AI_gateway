"""Garak Security Scanner REST API Server.

This server provides a REST API for running Garak security scans on LLM models.
It is designed to run as a standalone Docker container.
"""
import asyncio
import json
import os
import tempfile
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field


app = FastAPI(
    title="Garak Security Scanner",
    description="REST API for LLM security scanning using Garak",
    version="1.0.0"
)


# ============================================================================
# Models
# ============================================================================

class ScanRequest(BaseModel):
    model_name: str = Field(..., description="Name of the model to scan")
    generator_type: str = Field(default="openai", description="Type: openai, ollama, huggingface")
    api_base: Optional[str] = Field(default=None, description="API base URL")
    api_key: Optional[str] = Field(default=None, description="API key")
    categories: Optional[List[str]] = Field(default=None, description="Categories to test")
    scan_type: str = Field(default="quick", description="quick or standard")


class ScanResult(BaseModel):
    scan_id: str
    status: str
    model_name: str
    started_at: Optional[str]
    completed_at: Optional[str]
    results: Optional[Dict[str, Any]]


# In-memory scan storage
_scans: Dict[str, Dict] = {}
_scan_counter = 0


# ============================================================================
# Probe Configuration
# ============================================================================

GARAK_PROBE_MAPPING = {
    "prompt_injection": [
        "promptinject.HijackHateHumansMini",
        "promptinject.HijackKillHumansMini",
    ],
    "jailbreak": [
        "dan.Dan_11_0",
        "dan.Dan_6_0",
    ],
    "data_leakage": [
        "leakreplay.LiteratureCloze80",
    ],
    "toxicity": [
        "realtoxicityprompts.RTPBlank",
    ],
    "hallucination": [
        "packagehallucination.Python",
    ],
}

PROBE_SEVERITY = {
    "promptinject": "high",
    "dan": "critical",
    "leakreplay": "high",
    "realtoxicityprompts": "medium",
    "packagehallucination": "low",
}


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "garak-scanner"}


@app.get("/version")
async def get_version():
    """Get Garak version."""
    try:
        import garak
        return {"version": garak.__version__, "available": True}
    except ImportError:
        return {"version": None, "available": False}


@app.get("/categories")
async def list_categories():
    """List available scan categories."""
    categories = []
    for category, probes in GARAK_PROBE_MAPPING.items():
        categories.append({
            "id": category,
            "name": category.replace("_", " ").title(),
            "probe_count": len(probes),
        })
    return categories


@app.get("/probes")
async def list_probes():
    """List all available probes."""
    probes = []
    for category, probe_list in GARAK_PROBE_MAPPING.items():
        for probe in probe_list:
            probe_family = probe.split(".")[0]
            probes.append({
                "id": probe,
                "category": category,
                "name": probe.split(".")[-1],
                "severity": PROBE_SEVERITY.get(probe_family, "medium"),
            })
    return probes


@app.post("/scan")
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """Start a new security scan."""
    global _scan_counter
    _scan_counter += 1
    scan_id = f"scan_{_scan_counter}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    _scans[scan_id] = {
        "scan_id": scan_id,
        "status": "pending",
        "model_name": request.model_name,
        "started_at": None,
        "completed_at": None,
        "results": None,
    }
    
    background_tasks.add_task(
        run_scan_background,
        scan_id,
        request.model_name,
        request.generator_type,
        request.api_base,
        request.api_key,
        request.categories,
        request.scan_type,
    )
    
    return {"scan_id": scan_id, "status": "pending"}


@app.get("/scan/{scan_id}")
async def get_scan_result(scan_id: str):
    """Get scan result by ID."""
    if scan_id not in _scans:
        raise HTTPException(status_code=404, detail="Scan not found")
    return _scans[scan_id]


async def run_scan_background(
    scan_id: str,
    model_name: str,
    generator_type: str,
    api_base: Optional[str],
    api_key: Optional[str],
    categories: Optional[List[str]],
    scan_type: str,
):
    """Run Garak scan in background."""
    _scans[scan_id]["status"] = "running"
    _scans[scan_id]["started_at"] = datetime.utcnow().isoformat()
    
    try:
        # Determine probes to run
        if categories is None:
            categories = list(GARAK_PROBE_MAPPING.keys())
        
        probes_to_run = []
        for cat in categories:
            if cat in GARAK_PROBE_MAPPING:
                probes = GARAK_PROBE_MAPPING[cat]
                if scan_type == "quick":
                    probes_to_run.extend(probes[:1])
                else:
                    probes_to_run.extend(probes)
        
        # Build Garak command
        cmd = ["python", "-m", "garak"]
        
        if generator_type == "ollama":
            cmd.extend(["--model_type", "ollama"])
            cmd.extend(["--model_name", model_name])
            if api_base:
                os.environ["OLLAMA_HOST"] = api_base
        else:
            cmd.extend(["--model_type", "openai"])
            cmd.extend(["--model_name", model_name])
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
            if api_base:
                os.environ["OPENAI_API_BASE"] = api_base
        
        for probe in probes_to_run:
            cmd.extend(["--probes", probe])
        
        # Run in temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["GARAK_REPORT_DIR"] = tmpdir
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=tmpdir,
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=600
            )
            
            results = parse_garak_output(tmpdir, stdout.decode(), stderr.decode(), process.returncode)
        
        _scans[scan_id]["status"] = "completed" if process.returncode == 0 else "failed"
        _scans[scan_id]["results"] = results
        
    except asyncio.TimeoutError:
        _scans[scan_id]["status"] = "timeout"
        _scans[scan_id]["results"] = {"error": "Scan timed out"}
    except Exception as e:
        _scans[scan_id]["status"] = "failed"
        _scans[scan_id]["results"] = {"error": str(e)}
    
    _scans[scan_id]["completed_at"] = datetime.utcnow().isoformat()


def parse_garak_output(output_dir: str, stdout: str, stderr: str, return_code: int) -> Dict:
    """Parse Garak output."""
    results = {
        "vulnerabilities": [],
        "summary": {
            "total_probes": 0,
            "passed": 0,
            "failed": 0,
            "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        },
        "raw_output": stdout[:3000] if stdout else None,
    }
    
    if return_code != 0:
        results["error"] = stderr[:500] if stderr else "Unknown error"
    
    # Try to find JSON report
    try:
        report_files = list(Path(output_dir).glob("*.json"))
        if report_files:
            with open(report_files[0], 'r') as f:
                garak_report = json.load(f)
                # Parse report structure
                for probe_result in garak_report.get("probes", []):
                    passed = probe_result.get("passed", 0)
                    failed = probe_result.get("failed", 0)
                    results["summary"]["total_probes"] += passed + failed
                    results["summary"]["passed"] += passed
                    results["summary"]["failed"] += failed
    except Exception:
        pass
    
    return results


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
