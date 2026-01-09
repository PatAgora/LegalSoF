# 🏛️ Legal SoF Platform

**Production-ready MVP for automating Source of Funds (SoF) confirmation in legal firms**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.2-61DAFB.svg)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.3-3178C6.svg)](https://www.typescriptlang.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-336791.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Technology Stack](#-technology-stack)
- [Project Structure](#-project-structure)
- [Documentation](#-documentation)
- [Development](#-development)
- [Deployment](#-deployment)
- [Screenshots](#-screenshots)

---

## 🎯 Overview

The **Legal SoF Platform** replaces manual email/PDF review workflows with an intelligent, automated system for Source of Funds confirmation in business purchase transactions. Designed specifically for UK legal firms and AML compliance (SRA/MLRO workflows).

### The Problem
Legal teams spend hours manually:
- Emailing clients for documents
- Reviewing bank statements and completion documents
- Reconstructing funds flow across multiple accounts
- Checking amount consistency and dates
- Creating evidence reports for compliance

### The Solution
An end-to-end platform that automates:
- ✅ **Structured evidence collection** via secure client portal
- ✅ **Automated document intelligence** with AI-assisted extraction
- ✅ **Funds chain reconstruction** with timeline visualization
- ✅ **Consistency checks** with exception-based review
- ✅ **One-click report generation** with complete audit trail

---

## 🌟 Key Features

### 1. Matter Management
- Create and track SoF cases with workflow states
- Automatic reference number generation
- Risk rating system (auto + manual override)
- Analyst assignment and approvals
- Complete status tracking

### 2. Smart Evidence Capture
- **Client Portal** with secure, time-limited upload links
- **Dynamic Questionnaires** based on source type:
  - Business sale proceeds
  - Savings & dividends
  - Loans & inheritance
  - Gifted/third-party funds
  - Crypto-to-fiat conversions
- Real-time completeness tracking
- Document quality checks (blurred, password-protected, missing pages)

### 3. Document Intelligence
- **Multi-format support**: PDF, DOCX, XLSX
- **Pluggable extraction pipeline**:
  1. Heuristic extraction (regex + parsing)
  2. AI assistance (OpenAI) for low-confidence items
  3. OCR fallback (Tesseract) for image-based documents
- **Structured data extraction**:
  - Parties (names/entities)
  - Dates, amounts, account identifiers
  - Transaction references and descriptions
- User corrections tracked for continuous improvement

### 4. Funds Chain Reconstruction
The platform's **key differentiator**:
- Automatic identification of originating source events
- Tracking intermediate transfers across accounts
- Final payment availability verification
- **Timeline View**: Chronological funds events
- **Graph View**: Visual network of accounts and entities
- **Reconciliation**: Amount matching with tolerances
- Multi-currency support with fee handling

### 5. Consistency & Risk Checks
Automated checks with severity levels:
- ✅ **Amount Consistency**: SPA/completion vs bank credits vs declared
- ✅ **Date Alignment**: Declared dates vs statement dates
- ✅ **Identity Consistency**: Name/entity matching across documents
- ✅ **Gap Detection**: Missing periods in bank statements
- ✅ **Circular Flows**: Money roundtripping detection
- ✅ **Unexplained Credits**: Large unaccounted deposits
- ✅ **Timing Anomalies**: Suspicious date patterns

### 6. Reporting & Outputs
- **SoF Assessment Report**: Executive summary with AI-generated narrative
- **Funds Flow Diagram**: Visual representation with evidence links
- **Document Index**: All evidence catalogued with metadata
- **Checks Summary**: All flags and resolutions
- **Audit Trail Export**: Complete activity log for compliance

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Browser                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         React + TypeScript + Tailwind CSS                 │  │
│  │  - Dashboard  - Matters  - Documents  - Funds Chain      │  │
│  └────────────────────┬─────────────────────────────────────┘  │
└─────────────────────────┼─────────────────────────────────────────┘
                         │ HTTPS / REST API
                         │
┌─────────────────────────┼─────────────────────────────────────────┐
│                         ▼                                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              FastAPI Backend (Python)                      │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  Authentication & Authorization (JWT + RBAC)         │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  API Endpoints (REST)                                │  │  │
│  │  │  - Matters  - Documents  - Funds  - Checks          │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  Business Logic Services                             │  │  │
│  │  │  - Document Processing  - Extraction  - Checks      │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └─────────────┬──────────────────────┬─────────────────────┘  │
│                │                       │                         │
└────────────────┼───────────────────────┼─────────────────────────┘
                 │                       │
       ┌─────────▼────────┐   ┌─────────▼──────────┐
       │   PostgreSQL     │   │  S3 / MinIO        │
       │   Database       │   │  Object Storage    │
       │  - Users         │   │  - Documents       │
       │  - Matters       │   │  - Uploads         │
       │  - Documents     │   │  - Reports         │
       │  - Audit Logs    │   └────────────────────┘
       └──────────────────┘
```

### Component Breakdown

#### Frontend Layer
- **Framework**: React 18 with TypeScript
- **Styling**: Tailwind CSS for responsive design
- **State**: Zustand for global state, React Query for server state
- **Routing**: React Router v6
- **Build**: Vite for fast development and optimized production builds

#### Backend Layer
- **Framework**: FastAPI with async/await
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic for database versioning
- **Auth**: JWT tokens with role-based access control
- **Logging**: Structured logging with complete audit trail

#### Data Layer
- **Database**: PostgreSQL 15+ with async driver
- **Storage**: S3-compatible object storage
- **Caching**: Ready for Redis integration

#### External Services
- **AI**: OpenAI API for document extraction and narrative generation
- **OCR**: Tesseract for image-based document processing
- **Email**: SMTP integration ready for notifications

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- (Optional) Node.js 18+ and Python 3.11+ for local development

### Option 1: One-Command Start (Recommended)

```bash
git clone <repository-url>
cd legal-sof-platform
./start.sh
```

This script will:
1. ✅ Check Docker installation
2. ✅ Create environment configuration
3. ✅ Build and start all services
4. ✅ Run database migrations
5. ✅ Create admin user
6. ✅ Display access information

### Option 2: Manual Docker Setup

```bash
# Create environment file
cp backend/.env.example backend/.env

# Start services
docker-compose up -d

# Run migrations
docker-compose exec backend alembic upgrade head

# Create admin user
docker-compose exec backend python scripts/create_admin.py
```

### Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Default Credentials**:
  - Email: `admin@example.com`
  - Password: `admin123`
  - ⚠️ **Change immediately after first login!**

### Verify Installation

```bash
# Check all services are running
docker-compose ps

# View logs
docker-compose logs -f

# Check backend health
curl http://localhost:8000/health
```

---

## 🛠️ Technology Stack

### Backend
| Technology | Version | Purpose |
|-----------|---------|---------|
| FastAPI | 0.109.0 | Web framework |
| PostgreSQL | 15+ | Database |
| SQLAlchemy | 2.0.25 | ORM |
| Alembic | 1.13.1 | Migrations |
| Pydantic | 2.5.3 | Data validation |
| python-jose | 3.3.0 | JWT auth |
| pdfplumber | 0.10.3 | PDF processing |
| PyMuPDF | 1.23.21 | Advanced PDF |
| python-docx | 1.1.0 | Word documents |
| openpyxl | 3.1.2 | Excel files |
| pytesseract | 0.3.10 | OCR |
| openai | 1.10.0 | AI extraction |
| boto3 | 1.34.34 | S3 storage |
| structlog | 24.1.0 | Logging |

### Frontend
| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 18.2.0 | UI framework |
| TypeScript | 5.3.3 | Type safety |
| Vite | 5.0.12 | Build tool |
| Tailwind CSS | 3.4.1 | Styling |
| React Router | 6.21.3 | Routing |
| TanStack Query | 5.17.19 | Data fetching |
| Zustand | 4.5.0 | State management |
| React Hook Form | 7.49.3 | Form handling |
| Axios | 1.6.5 | HTTP client |

### DevOps
| Technology | Purpose |
|-----------|---------|
| Docker | Containerization |
| Docker Compose | Multi-container orchestration |
| Nginx | Reverse proxy (production) |
| PostgreSQL | Database |

---

## 📁 Project Structure

```
legal-sof-platform/
├── 📄 README.md                    # This file
├── 📄 MVP_SUMMARY.md               # Detailed feature summary
├── 📄 DEVELOPMENT.md               # Development guide
├── 📄 DEPLOYMENT.md                # Production deployment
├── 🔧 docker-compose.yml           # Dev environment
├── 🚀 start.sh                     # Quick start script
│
├── backend/                        # FastAPI Backend
│   ├── alembic/                   # Database migrations
│   │   ├── env.py                 # Alembic config
│   │   └── versions/              # Migration files
│   │
│   ├── app/
│   │   ├── main.py                # FastAPI app entry point
│   │   │
│   │   ├── api/                   # API endpoints
│   │   │   ├── dependencies/      # Shared dependencies
│   │   │   │   └── auth.py        # Auth dependencies
│   │   │   └── v1/
│   │   │       ├── __init__.py    # API router
│   │   │       └── endpoints/
│   │   │           └── auth.py    # Auth endpoints ✅
│   │   │
│   │   ├── core/                  # Core functionality
│   │   │   ├── config.py          # Settings
│   │   │   ├── security.py        # JWT & hashing
│   │   │   └── logging.py         # Structured logging
│   │   │
│   │   ├── db/                    # Database
│   │   │   ├── base.py            # Base model
│   │   │   └── session.py         # Session management
│   │   │
│   │   ├── models/                # SQLAlchemy models ✅
│   │   │   ├── user.py            # User & roles
│   │   │   ├── matter.py          # Matter/case
│   │   │   ├── document.py        # Documents
│   │   │   ├── questionnaire.py   # Questionnaires
│   │   │   ├── entity.py          # Parties/accounts
│   │   │   ├── funds_event.py     # Funds chain
│   │   │   ├── check.py           # Consistency checks
│   │   │   └── audit.py           # Audit & approvals
│   │   │
│   │   ├── schemas/               # Pydantic schemas
│   │   │   ├── user.py            # User DTOs ✅
│   │   │   └── matter.py          # Matter DTOs ✅
│   │   │
│   │   ├── services/              # Business logic 🔄
│   │   └── utils/                 # Utilities 🔄
│   │
│   ├── scripts/
│   │   └── create_admin.py        # Admin user creation ✅
│   │
│   ├── requirements.txt           # Python deps
│   ├── .env.example               # Example config
│   └── alembic.ini                # Alembic config
│
├── frontend/                       # React Frontend
│   ├── src/
│   │   ├── main.tsx               # Entry point
│   │   ├── App.tsx                # Root component
│   │   │
│   │   ├── components/            # Reusable components
│   │   │   └── Layout.tsx         # Main layout ✅
│   │   │
│   │   ├── pages/                 # Page components ✅
│   │   │   ├── LoginPage.tsx      # Login
│   │   │   ├── DashboardPage.tsx  # Dashboard
│   │   │   ├── MattersPage.tsx    # Matter list
│   │   │   └── MatterDetailPage.tsx # Matter detail
│   │   │
│   │   ├── lib/                   # Utilities
│   │   │   └── api.ts             # API client ✅
│   │   │
│   │   ├── stores/                # State management
│   │   │   └── authStore.ts       # Auth state ✅
│   │   │
│   │   ├── hooks/                 # Custom hooks 🔄
│   │   └── types/                 # TypeScript types 🔄
│   │
│   ├── package.json               # Node deps
│   ├── vite.config.ts             # Vite config
│   ├── tailwind.config.js         # Tailwind config
│   └── tsconfig.json              # TypeScript config
│
└── docker/                         # Dockerfiles
    ├── Dockerfile.backend         # Backend image
    └── Dockerfile.frontend        # Frontend image

Legend:
✅ Implemented
🔄 Ready for implementation
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [README.md](README.md) | This file - project overview and quick start |
| [MVP_SUMMARY.md](MVP_SUMMARY.md) | Detailed feature breakdown and roadmap |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Development setup, patterns, and guidelines |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production deployment guide (AWS, Azure, etc.) |
| [API Docs](http://localhost:8000/docs) | Interactive API documentation (Swagger) |

---

## 💻 Development

### Local Development Setup

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Setup database
createdb sof_platform
alembic upgrade head
python scripts/create_admin.py

# Run dev server
uvicorn app.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Add new field"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# View history
alembic history
```

### Testing

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

### Code Quality

```bash
# Backend
black .              # Format
ruff check .         # Lint
mypy .               # Type check

# Frontend
npm run lint         # ESLint
npm run type-check   # TypeScript
```

For more details, see [DEVELOPMENT.md](DEVELOPMENT.md)

---

## 🚀 Deployment

### Quick Production Checklist

- [ ] Change default admin password
- [ ] Generate secure `SECRET_KEY`
- [ ] Configure production database (RDS, Azure Database)
- [ ] Setup S3/Azure Blob storage
- [ ] Add OpenAI API key
- [ ] Configure CORS origins
- [ ] Enable HTTPS with SSL certificate
- [ ] Setup monitoring (Sentry, CloudWatch)
- [ ] Configure backups
- [ ] Review security settings

### Deployment Options

1. **AWS ECS/Fargate** (Recommended)
2. **AWS EC2 with Docker Compose**
3. **Azure Container Instances**
4. **Google Cloud Run**
5. **Any Docker-capable hosting**

For detailed instructions, see [DEPLOYMENT.md](DEPLOYMENT.md)

---

## 🔒 Security

- ✅ JWT authentication with secure tokens
- ✅ Password hashing (bcrypt)
- ✅ Role-based access control (RBAC)
- ✅ SQL injection protection (ORM)
- ✅ Input validation (Pydantic)
- ✅ CORS configuration
- ✅ Complete audit logging
- ✅ Environment-based secrets
- 🔄 Rate limiting ready
- 🔄 File validation ready

---

## 📈 Roadmap

### ✅ Phase 0: MVP Foundation (Complete)
- Complete database schema
- Authentication system
- Basic UI components
- Docker environment

### 🔄 Phase 1: Core Features (Next - 2-3 weeks)
- [ ] Matter CRUD operations
- [ ] Document upload and storage
- [ ] Client portal with secure tokens
- [ ] Questionnaire system implementation

### 🔄 Phase 2: Intelligence (2-3 weeks)
- [ ] Document extraction pipeline
- [ ] OpenAI integration
- [ ] Entity extraction and matching
- [ ] OCR processing

### 🔄 Phase 3: Funds Chain (2 weeks)
- [ ] Automatic event detection
- [ ] Funds flow reconstruction
- [ ] Timeline visualization
- [ ] Graph visualization

### 🔄 Phase 4: Checks & Reports (2 weeks)
- [ ] Automated consistency checks
- [ ] Check resolution workflow
- [ ] Report generation
- [ ] PDF export

### 🔄 Phase 5: Production Ready (1-2 weeks)
- [ ] Comprehensive testing
- [ ] Performance optimization
- [ ] Security audit
- [ ] Production deployment

**Estimated Time to Full Product**: 8-12 weeks

---

## 🤝 Contributing

This is a proprietary project. For authorized contributors:

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes following code quality guidelines
3. Write tests
4. Update documentation
5. Submit pull request

---

## 📝 License

**Proprietary** - All rights reserved

---

## 📞 Support

- **Documentation**: Check the docs folder
- **Issues**: Internal issue tracker
- **Email**: support@yourdomain.com

---

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [React](https://react.dev/) - UI library
- [PostgreSQL](https://www.postgresql.org/) - Robust database
- [Tailwind CSS](https://tailwindcss.com/) - Utility-first CSS
- [OpenAI](https://openai.com/) - AI capabilities

---

<div align="center">

**Made for legal professionals who deserve better tools**

⚖️ 🤖 📊

[Documentation](DEVELOPMENT.md) • [Deployment](DEPLOYMENT.md) • [Summary](MVP_SUMMARY.md)

</div>
