"""
Source of Funds Assessment API Endpoints

100% LOCAL - No external API calls
Handles file uploads, processing, and SoF assessment results
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from app.db.session import get_db
from app.services.file_processor import file_processor
from app.services.sof_assessment_engine import SoFAssessmentEngine
from app.models import Matter

router = APIRouter()


# Sync DB helper (for blocking file operations)
def get_sync_db():
    """Get synchronous database session for blocking operations"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    
    db_url = str(settings.DATABASE_URL).replace("sqlite+aiosqlite", "sqlite")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# In-memory storage for assessment data (per matter)
# In production, this would be stored in database
assessment_storage: Dict[int, Dict[str, Any]] = {}


@router.post("/matters/{matter_id}/sof-assessment/upload")
async def upload_sof_files(
    matter_id: int,
    file: UploadFile = File(...),
    file_category: str = Form(...),  # 'client_info', 'bank_statement', 'supporting_doc'
    db: Session = Depends(get_sync_db)
):
    """
    Upload and process a file for SoF assessment
    
    File categories:
    - client_info: JSON with client details, purchase info, SoF explanation
    - bank_statement: CSV or PDF bank statement
    - supporting_doc: PDF supporting document
    """
    
    # Verify matter exists
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    # Initialize storage for this matter if needed
    if matter_id not in assessment_storage:
        assessment_storage[matter_id] = {
            "client_info": None,
            "bank_statements": [],
            "supporting_docs": [],
            "uploaded_files": [],
            "status": "pending",
            "last_updated": None
        }
    
    # Determine file type from extension and MIME
    file_ext = file.filename.split('.')[-1].lower() if file.filename else ''
    
    if file_category == 'client_info':
        if file_ext != 'json':
            raise HTTPException(
                status_code=400, 
                detail="Client info must be JSON file"
            )
        file_type = 'json'
    
    elif file_category == 'bank_statement':
        if file_ext == 'csv':
            file_type = 'csv'
        elif file_ext == 'pdf':
            file_type = 'pdf'
        else:
            raise HTTPException(
                status_code=400,
                detail="Bank statement must be CSV or PDF"
            )
    
    elif file_category == 'supporting_doc':
        if file_ext != 'pdf':
            raise HTTPException(
                status_code=400,
                detail="Supporting documents must be PDF"
            )
        file_type = 'pdf'
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file category: {file_category}"
        )
    
    # Process the file
    result = await file_processor.process_upload(file, file_type)
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=f"File processing failed: {result['error']}"
        )
    
    # Store the processed data
    storage = assessment_storage[matter_id]
    
    if file_category == 'client_info':
        storage['client_info'] = result['data']
    
    elif file_category == 'bank_statement':
        # Merge bank statements
        new_transactions = result['data']['bank_statements']
        storage['bank_statements'].extend(new_transactions)
    
    elif file_category == 'supporting_doc':
        storage['supporting_docs'].append(result['data'])
    
    # Track uploaded file
    storage['uploaded_files'].append({
        "filename": file.filename,
        "category": file_category,
        "file_type": result['file_type'],
        "uploaded_at": datetime.utcnow().isoformat(),
        "records_count": result['data'].get('transaction_count') or 1
    })
    
    storage['last_updated'] = datetime.utcnow().isoformat()
    storage['status'] = 'files_uploaded'
    
    return {
        "success": True,
        "matter_id": matter_id,
        "file_category": file_category,
        "filename": file.filename,
        "records_processed": result['data'].get('transaction_count') or 1,
        "message": f"File processed successfully"
    }


@router.get("/matters/{matter_id}/sof-assessment/status")
async def get_sof_assessment_status(
    matter_id: int,
    db: Session = Depends(get_sync_db)
):
    """
    Get current status of SoF assessment for a matter
    """
    
    # Verify matter exists
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    # Get assessment data
    if matter_id not in assessment_storage:
        return {
            "matter_id": matter_id,
            "status": "no_data",
            "uploaded_files": [],
            "ready_for_assessment": False
        }
    
    storage = assessment_storage[matter_id]
    
    # Check if ready for assessment
    has_client_info = storage['client_info'] is not None
    has_bank_statements = len(storage['bank_statements']) > 0
    ready = has_client_info and has_bank_statements
    
    return {
        "matter_id": matter_id,
        "status": storage['status'],
        "uploaded_files": storage['uploaded_files'],
        "files_summary": {
            "client_info": "uploaded" if has_client_info else "missing",
            "bank_statements_count": len(storage['bank_statements']),
            "supporting_docs_count": len(storage['supporting_docs'])
        },
        "ready_for_assessment": ready,
        "last_updated": storage['last_updated']
    }


@router.post("/matters/{matter_id}/sof-assessment/run")
async def run_sof_assessment(
    matter_id: int,
    db: Session = Depends(get_sync_db)
):
    """
    Run SoF assessment engine on uploaded data
    Integrates with Transaction Review automatically
    """
    
    # Verify matter exists
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    # Get assessment data
    if matter_id not in assessment_storage:
        raise HTTPException(
            status_code=400,
            detail="No files uploaded for this matter"
        )
    
    storage = assessment_storage[matter_id]
    
    # Validate required data
    if not storage['client_info']:
        raise HTTPException(
            status_code=400,
            detail="Client info file required (JSON with client details, purchase, SoF explanation)"
        )
    
    if not storage['bank_statements']:
        raise HTTPException(
            status_code=400,
            detail="At least one bank statement file required (CSV or PDF)"
        )
    
    # Extract data
    client_info = storage['client_info']['client_info']
    purchase = storage['client_info']['purchase']
    sof_explanation = storage['client_info']['sof_explanation']
    bank_statements = storage['bank_statements']
    known_documents = storage['client_info'].get('known_documents', [])
    supporting_docs_data = storage['supporting_docs']  # Full document data with extracted info
    
    # Add uploaded supporting docs to known documents
    for doc in storage['supporting_docs']:
        doc_type = doc.get('document_type', 'unknown')
        if doc_type != 'unknown':
            known_documents.append(doc_type)
    
    flags = storage['client_info'].get('flags', {})
    constraints = storage['client_info'].get('constraints', {})
    
    # DEBUG LOGGING
    print(f"\n=== SoF ASSESSMENT DEBUG ===")
    print(f"Matter ID: {matter_id}")
    print(f"Supporting docs uploaded: {len(supporting_docs_data)}")
    for idx, doc in enumerate(supporting_docs_data):
        print(f"  Doc {idx}: Type={doc.get('document_type')}, Has extracted_data={bool(doc.get('extracted_data'))}")
        if doc.get('extracted_data'):
            print(f"    Extracted fields: {list(doc.get('extracted_data', {}).keys())}")
    print(f"Known documents: {known_documents}")
    print(f"===========================\n")
    
    # Run assessment engine
    engine = SoFAssessmentEngine(matter_id=matter_id, db=db)
    
    try:
        assessment_result = engine.assess(
            client_info=client_info,
            purchase=purchase,
            sof_explanation=sof_explanation,
            bank_statements=bank_statements,
            known_documents=known_documents,
            supporting_docs_data=supporting_docs_data,  # Pass full document data
            constraints=constraints,
            flags=flags
        )
        
        # Store result
        storage['assessment_result'] = assessment_result
        storage['status'] = 'completed'
        storage['last_updated'] = datetime.utcnow().isoformat()
        
        return {
            "success": True,
            "matter_id": matter_id,
            "assessment": assessment_result
        }
    
    except Exception as e:
        storage['status'] = 'error'
        storage['error'] = str(e)
        raise HTTPException(
            status_code=500,
            detail=f"Assessment engine error: {str(e)}"
        )


@router.get("/matters/{matter_id}/sof-assessment/results")
async def get_sof_assessment_results(
    matter_id: int,
    db: Session = Depends(get_sync_db)
):
    """
    Get full SoF assessment results
    """
    
    # Verify matter exists
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    # Get assessment data
    if matter_id not in assessment_storage:
        raise HTTPException(
            status_code=404,
            detail="No assessment data found for this matter"
        )
    
    storage = assessment_storage[matter_id]
    
    if storage['status'] != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Assessment not completed (status: {storage['status']})"
        )
    
    return {
        "matter_id": matter_id,
        "assessment": storage['assessment_result'],
        "metadata": {
            "uploaded_files": storage['uploaded_files'],
            "bank_statements_count": len(storage['bank_statements']),
            "supporting_docs_count": len(storage['supporting_docs']),
            "completed_at": storage['last_updated']
        }
    }


@router.get("/matters/{matter_id}/sof-assessment/file-note")
async def download_file_note(
    matter_id: int,
    db: Session = Depends(get_sync_db)
):
    """
    Download audit-ready file note as plain text
    """
    
    # Verify matter exists
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    # Get assessment data
    if matter_id not in assessment_storage:
        raise HTTPException(
            status_code=404,
            detail="No assessment data found for this matter"
        )
    
    storage = assessment_storage[matter_id]
    
    if storage['status'] != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Assessment not completed (status: {storage['status']})"
        )
    
    # Get file note
    file_note = storage['assessment_result']['file_note_summary']
    
    from fastapi.responses import PlainTextResponse
    
    return PlainTextResponse(
        content=file_note,
        headers={
            "Content-Disposition": f"attachment; filename=sof_file_note_matter_{matter_id}.txt"
        }
    )


@router.delete("/matters/{matter_id}/sof-assessment/reset")
async def reset_sof_assessment(
    matter_id: int,
    db: Session = Depends(get_sync_db)
):
    """
    Reset/clear SoF assessment data for a matter
    """
    
    # Verify matter exists
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    # Clear storage
    if matter_id in assessment_storage:
        del assessment_storage[matter_id]
    
    return {
        "success": True,
        "matter_id": matter_id,
        "message": "SoF assessment data cleared"
    }
