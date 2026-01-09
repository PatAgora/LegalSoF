# Legal SoF (Source of Funds) Automation Platform

Production-ready MVP web application that automates legal firms' Source of Funds confirmation process for business purchases.

## 🎯 Core Value Proposition

Replace manual email/PDF review with:
- Structured evidence collection via client portal
- Automated document intelligence & extraction
- Funds chain reconstruction & timeline visualization
- Consistency checks & exception-based review
- One-click SoF report pack generation
- Complete audit trail

## 🏗️ Architecture

### Frontend
- **Tech**: React 18 + TypeScript + Tailwind CSS + Vite
- **Features**: Matter management, client portal, document viewer, funds flow visualization
- **Auth**: JWT-based with role-based access control

### Backend
- **Tech**: FastAPI (Python 3.11+) + async endpoints
- **Database**: PostgreSQL 15+ with SQLAlchemy 2.0 + Alembic migrations
- **Storage**: S3-compatible interface (local disk for dev)
- **Processing**: pdfplumber, PyMuPDF, python-docx, openpyxl, Tesseract OCR
- **AI**: OpenAI API for extraction assistance + summarization + SoF narrative generation

### Infrastructure
- **Dev**: Docker Compose
- **Observability**: Structured logging + audit log table
- **Security**: JWT auth, role-based access, secure upload tokens

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for local frontend dev)
- Python 3.11+ (for local backend dev)

### Development Setup

```bash
# Clone and navigate
cd /home/user/webapp

# Start all services (PostgreSQL + Backend + Frontend)
docker-compose up -d

# Backend will be available at: http://localhost:8000
# Frontend will be available at: http://localhost:5173
# API docs at: http://localhost:8000/docs
```

### Initial Setup

```bash
# Run database migrations
docker-compose exec backend alembic upgrade head

# Create initial admin user
docker-compose exec backend python scripts/create_admin.py
```

## 👥 User Roles

- **Analyst**: Create matters, review documents, manage checks
- **Partner**: Approve matters, override risk ratings
- **Admin**: User management, system configuration

## 📋 Core Features

### 1. Matter Management
- Create matters with client details, transaction info, risk rating
- Track status through workflow stages
- Assign analysts and manage approvals

### 2. Smart Evidence Capture (Client Portal)
- Secure, tokenized upload links (time-limited)
- Dynamic questionnaire based on source type:
  - Business sale proceeds
  - Savings
  - Dividends
  - Loan
  - Inheritance
  - Gifted/third-party funds
  - Crypto-to-fiat
- Real-time completeness tracking
- Document quality checks (blurred, password-protected, missing pages)

### 3. Document Intelligence
- Multi-format support: PDF, DOCX, XLSX
- Pluggable extraction pipeline:
  1. Heuristic extraction (regex + parsing)
  2. AI assistance for low-confidence items
  3. OCR fallback for image-based documents
- Structured data extraction:
  - Parties (names/entities)
  - Dates, amounts, account identifiers
  - Transaction references and descriptions
- User corrections with override tracking

### 4. Funds Chain Reconstruction
- Automatic funds flow building:
  - Originating source events
  - Intermediate transfers
  - Final payment availability
- Visualizations:
  - Timeline view
  - Graph view (accounts/entities as nodes)
  - Reconciled amounts with tolerances
- Multi-currency support with fees
- Manual event editing and evidence linking

### 5. Consistency & Risk Checks
Automated checks with severity levels:
- **Amount consistency**: SPA/completion vs bank credits vs declared
- **Date alignment**: Declared dates vs statement dates
- **Identity consistency**: Name/entity matching across documents
- **Source legitimacy**: Pattern detection for unusual sources
- **Gap detection**: Missing periods in bank statements
- **Circular flows**: Money roundtripping detection

### 6. Outputs
- **SoF Assessment Report**: Executive summary with AI-generated narrative
- **Funds Flow Diagram**: Visual representation with evidence links
- **Document Index**: All evidence catalogued
- **Checks Summary**: All flags and resolutions
- **Audit Trail Export**: Complete activity log

## 🔒 Security & Compliance

- UK legal/AML context (SRA/MLRO workflows)
- Data minimization and redaction options
- Complete audit trail for all actions
- Secure document storage with encryption
- Time-limited client portal access
- Role-based access control

## 📊 API Documentation

FastAPI automatically generates interactive API docs:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test

# E2E tests
npm run test:e2e
```

## 📦 Production Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for:
- AWS/Azure deployment guides
- Environment configuration
- Scaling considerations
- Backup strategies
- Monitoring setup

## 🛠️ Development

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

## 📝 License

Proprietary - All rights reserved

## 🤝 Support

For support, contact your system administrator.
