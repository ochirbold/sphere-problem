"""
main.py - CVP Formula Engine API

This module provides a FastAPI-based REST API for CVP formula execution.
It includes endpoints for:
1. Formula engine execution (database-driven and direct)
2. Health checks and system monitoring

This version focuses only on the formula engine API endpoints.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import subprocess
import os
import json
import tempfile

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="CVP Formula Engine API",
    version="2.0.0",
    description="API for Cost-Volume-Profit formula execution",
    docs_url="/docs",
    redoc_url="/redoc"
)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class FormulaRequest(BaseModel):
    """Request model for database-driven formula execution."""
    
    indicator_id: int = Field(..., description="Database indicator ID")
    id_column: str = Field("ID", description="ID column name in database")
    formulas: Optional[List[str]] = Field(
        None, 
        description="Optional manual formulas to override database ones"
    )


class DirectFormulaRequest(BaseModel):
    """Request model for direct formula execution without database."""
    
    table_name: str = Field(..., description="Table name (for reference only)")
    id_column: str = Field(..., description="ID column name")
    formulas: Dict[str, str] = Field(..., description="Dictionary of target:expression formulas")
    data: List[Dict[str, Any]] = Field(..., description="Row data for calculation")


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    status: str = Field("ERROR", description="Error status")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class SuccessResponse(BaseModel):
    """Standard success response model."""
    
    status: str = Field("OK", description="Success status")
    message: Optional[str] = Field(None, description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")


# ============================================================================
# CVP FORMULA ENGINE API ENDPOINTS
# ============================================================================

@app.post("/formula/calculate")
async def calculate_formulas(request: FormulaRequest):
    """
    Execute CVP formulas for given indicator_id (subprocess wrapper)
    """
    try:
        # Build command
        cmd = ["python", "formula/pythoncode.py", str(request.indicator_id), request.id_column]
        
        # Add manual formulas if provided
        if request.formulas:
            cmd.extend(request.formulas)
        
        # Get current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Execute from current directory
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=current_dir
        )
        
        # Parse output
        if result.returncode == 0:
            # Extract results from output
            lines = result.stdout.split('\n')
            updated_rows = 0
            errors = 0
            
            for line in lines:
                if "Updated rows:" in line:
                    updated_rows = int(line.split(":")[1].strip())
                elif "Errors:" in line:
                    errors = int(line.split(":")[1].strip())
            
            return {
                "success": True,
                "updated_rows": updated_rows,
                "errors": errors,
                "output": result.stdout,
                "command": " ".join(cmd)
            }
        else:
            return {
                "success": False,
                "updated_rows": 0,
                "errors": 1,
                "error": result.stderr,
                "output": result.stdout,
                "command": " ".join(cmd)
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/formula/calculate/direct")
async def calculate_direct_formulas(request: DirectFormulaRequest):
    """
    Direct CVP calculation without database dependency
    Note: This requires refactoring PYTHONCODE.PY to expose core functions
    """
    try:
        # For now, we'll use subprocess with a temporary file
        import tempfile
        
        # Create temporary data file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            data = {
                "table_name": request.table_name,
                "id_column": request.id_column,
                "formulas": request.formulas,
                "data": request.data
            }
            json.dump(data, f)
            temp_file = f.name
        
        try:
            # This would call a refactored version of the formula engine
            # For now, return a placeholder response
            return {
                "success": True,
                "message": "Direct calculation endpoint - requires refactoring",
                "note": "Need to extract core logic from PYTHONCODE.PY into reusable functions",
                "data_summary": {
                    "table": request.table_name,
                    "rows": len(request.data),
                    "formulas": len(request.formulas)
                }
            }
        finally:
            # Clean up temp file
            if os.path.exists(temp_file):
                os.unlink(temp_file)
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/formula/health")
async def formula_health():
    """Health check for formula engine"""
    return {
        "status": "healthy",
        "service": "CVP Formula Engine API",
        "version": "2.0.0",
        "endpoints": [
            "POST /formula/calculate",
            "POST /formula/calculate/direct",
            "GET /formula/health"
        ]
    }


@app.get("/health")
async def health():
    """Overall API health check"""
    return {
        "status": "healthy",
        "service": "CVP Optimization & Formula Engine API",
        "version": "2.0.0"
    }


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/")
async def root():
    return {
        "message": "CVP Optimization & Formula Engine API",
        "version": "2.0.0",
        "documentation": "/docs",
        "endpoints": {
            "optimization": {
                "POST /optimize": "CVP optimization (volume, price, cost, robust)"
            },
            "formula_engine": {
                "POST /formula/calculate": "Execute CVP formulas from database",
                "POST /formula/calculate/direct": "Direct calculation with provided data",
                "GET /formula/health": "Formula engine health check"
            },
            "system": {
                "GET /health": "Overall API health",
                "GET /": "This documentation"
            }
        }
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)