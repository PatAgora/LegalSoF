# CRITICAL BUG FIX: Persistent Storage for Assessment Data

## The Problem

**Root Cause:** Backend running with `--reload` flag was auto-restarting whenever code changes were detected, **wiping out the in-memory `assessment_storage` dictionary**.

### What Was Happening

1. User uploads client_info.json → ✅ Stored in memory
2. User uploads bank_statement.csv → ✅ Stored in memory  
3. User runs assessment → ✅ Works fine (INSUFFICIENT)
4. User uploads PDF 1 → ✅ Stored in memory
5. User uploads PDF 2 → ✅ Stored in memory
6. **Backend auto-restarts** (due to file watch) → ❌ **ALL DATA LOST**
7. User runs assessment → ❌ 0 supporting docs, same INSUFFICIENT result

### Evidence

From backend logs:
```
INFO: Application startup complete.
INFO: Shutting down
INFO: Application startup complete.  ← Restart wipes memory!
INFO: Shutting down
INFO: Application startup complete.
```

And assessment logs:
```
Supporting docs uploaded: 2  ← Data exists
... backend restarts ...
Supporting docs uploaded: 0  ← Data GONE!
```

---

## The Solution

**Implemented file-based persistent storage** that survives backend restarts.

### Changes Made

**File:** `backend/app/api/v1/endpoints/sof_assessment.py`

1. **Added persistence functions:**
   ```python
   STORAGE_FILE = Path("/tmp/sof_assessment_storage.json")
   
   def load_storage() -> Dict[int, Dict[str, Any]]:
       """Load storage from file"""
       if STORAGE_FILE.exists():
           try:
               with open(STORAGE_FILE, 'r') as f:
                   return json.load(f)
           except:
               return {}
       return {}
   
   def save_storage(storage: Dict[int, Dict[str, Any]]):
       """Save storage to file"""
       storage_str_keys = {str(k): v for k, v in storage.items()}
       with open(STORAGE_FILE, 'w') as f:
           json.dump(storage_str_keys, f)
   ```

2. **Load storage on module import:**
   ```python
   assessment_storage = load_storage()
   assessment_storage = {int(k): v for k, v in assessment_storage.items()}
   ```

3. **Save after every data modification:**
   - After file upload: `save_storage(assessment_storage)`
   - After assessment run: `save_storage(assessment_storage)`
   - After reset: `save_storage(assessment_storage)`

---

## How It Works Now

### Storage Lifecycle

```
┌─────────────────────────────────────────────┐
│  1. Module loads                            │
│     → load_storage() reads from file       │
│     → assessment_storage restored           │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  2. User uploads files                      │
│     → Data stored in assessment_storage     │
│     → save_storage() persists to file       │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  3. Backend restarts (auto-reload)          │
│     → Memory cleared                        │
│     → Module loads again                    │
│     → load_storage() restores data          │
│     → ✅ NO DATA LOSS!                      │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  4. User runs assessment                    │
│     → Data still present                    │
│     → PDFs processed correctly              │
│     → ✅ VERIFICATION WORKS!                │
└─────────────────────────────────────────────┘
```

---

## Test Results

### Before Fix
```
Step 3: Check status before PDFs...
   Supporting docs: 0  ✅

Step 7: Check status after PDFs...
   Supporting docs: 2  ✅

... backend restart ...

Step 8: Running SECOND assessment...
   Supporting docs: 0  ❌ DATA LOST!
```

### After Fix
```
Step 3: Check status before PDFs...
   Supporting docs: 0  ✅

Step 7: Check status after PDFs...
   Supporting docs: 2  ✅

... backend restart ...

Step 8: Running SECOND assessment...
   Supporting docs: 2  ✅ DATA PERSISTED!
   
   Claim 0: Inheritance - ✅ VERIFIED (100% confidence)
   Claim 1: Property Sale - ✅ VERIFIED (83% confidence)
```

---

## Why This Happened

The original code comment said:
```python
# In-memory storage for assessment data (per matter)
# In production, this would be stored in database
assessment_storage: Dict[int, Dict[str, Any]] = {}
```

In **development** with `--reload`, the backend restarts frequently:
- File saves during editing
- Code changes trigger auto-reload
- Each restart = fresh Python process = empty dict

The user experienced this as: "PDFs not being considered" when actually **data was being lost on restart**.

---

## Production Considerations

### Current Solution (File-based)
- ✅ Works in development with auto-reload
- ✅ Simple implementation
- ✅ No external dependencies
- ⚠️ Not suitable for multi-process deployment
- ⚠️ Not suitable for horizontal scaling

### Future Enhancement Options

For production deployment:

1. **Database Storage** (Recommended)
   - Store assessment data in PostgreSQL/SQLite
   - Survives all restarts
   - Supports multi-process
   - Provides audit trail

2. **Redis Cache**
   - Fast in-memory with persistence
   - Supports multi-process
   - Auto-expiration options

3. **Session Storage**
   - Use secure session tokens
   - Store in database with session ID
   - Better for multi-user systems

---

## Deployment Notes

### Development Environment
- ✅ Current file-based solution works perfectly
- ✅ Survives `--reload` restarts
- ✅ Allows rapid development iteration

### Production Environment
- ⚠️ Replace with database storage
- Remove `--reload` flag
- Use process manager (pm2, supervisor, gunicorn workers)

---

## Impact

- ✅ **PDF extraction working** (was always working)
- ✅ **Document verification working** (was always working)
- ✅ **Assessment persistence FIXED** (was broken due to restarts)
- ✅ **User workflow now works correctly:**
  1. Upload initial docs
  2. Run assessment → INSUFFICIENT
  3. Add PDFs
  4. Run assessment → ✅ **VERIFIED** (PDFs are now considered!)

---

## Summary

The issue was **NOT** with PDF extraction or verification - those were working perfectly all along! 

The issue was **data persistence** - the backend was losing uploaded data on restart, causing the second assessment to run with 0 supporting docs.

**File-based persistence now ensures data survives backend restarts** during development.

---

**Date:** 2026-01-12  
**Bug:** Assessment data lost on backend restart  
**Fix:** File-based persistent storage  
**Status:** ✅ RESOLVED
