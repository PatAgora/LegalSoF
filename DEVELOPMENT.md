# Development Guide - Legal SoF Platform

## Project Structure

```
legal-sof-platform/
├── backend/                    # FastAPI backend
│   ├── alembic/               # Database migrations
│   ├── app/
│   │   ├── api/               # API endpoints
│   │   │   ├── dependencies/  # Shared dependencies
│   │   │   └── v1/           # API v1 routes
│   │   ├── core/             # Core functionality
│   │   ├── db/               # Database configuration
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   └── utils/            # Utility functions
│   ├── scripts/              # Utility scripts
│   ├── tests/                # Backend tests
│   └── requirements.txt      # Python dependencies
├── frontend/                  # React frontend
│   ├── src/
│   │   ├── components/       # Reusable components
│   │   ├── pages/            # Page components
│   │   ├── lib/              # Utilities & API client
│   │   ├── hooks/            # Custom React hooks
│   │   ├── stores/           # Zustand state stores
│   │   └── types/            # TypeScript types
│   └── package.json          # Node dependencies
├── docker/                    # Docker configuration
├── docker-compose.yml         # Development setup
└── README.md                  # Project documentation
```

## Development Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or use Docker)
- Git

### Backend Development

1. **Create virtual environment:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Setup database:**
```bash
# If using local PostgreSQL
createdb sof_platform

# Run migrations
alembic upgrade head

# Create admin user
python scripts/create_admin.py
```

4. **Run development server:**
```bash
uvicorn app.main:app --reload --port 8000
```

5. **Access API docs:**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

### Frontend Development

1. **Install dependencies:**
```bash
cd frontend
npm install
```

2. **Run development server:**
```bash
npm run dev
```

3. **Access application:**
   - Frontend: http://localhost:5173
   - Connects to backend at http://localhost:8000

### Using Docker (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Database Migrations

### Creating a new migration

```bash
cd backend
alembic revision --autogenerate -m "Add new field to Matter"
```

### Applying migrations

```bash
# Upgrade to latest
alembic upgrade head

# Upgrade one version
alembic upgrade +1

# Downgrade one version
alembic downgrade -1

# View current version
alembic current

# View history
alembic history
```

## API Development

### Adding a new endpoint

1. **Create schema in `app/schemas/`:**
```python
from pydantic import BaseModel

class DocumentCreate(BaseModel):
    matter_id: int
    filename: str
    document_type: str
```

2. **Create endpoint in `app/api/v1/endpoints/`:**
```python
from fastapi import APIRouter, Depends
from app.schemas.document import DocumentCreate

router = APIRouter()

@router.post("/documents")
async def create_document(
    data: DocumentCreate,
    db: AsyncSession = Depends(get_db),
):
    # Implementation
    pass
```

3. **Register router in `app/api/v1/__init__.py`:**
```python
from app.api.v1.endpoints import documents

api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["documents"]
)
```

### Authentication

All protected endpoints should use the authentication dependency:

```python
from app.api.dependencies.auth import get_current_active_user
from app.models.user import User

@router.get("/protected")
async def protected_route(
    current_user: User = Depends(get_current_active_user),
):
    return {"user_id": current_user.id}
```

Role-based access:

```python
from app.api.dependencies.auth import require_partner

@router.post("/approve")
async def approve_matter(
    current_user: User = Depends(require_partner),
):
    # Only partners and admins can access
    pass
```

## Frontend Development

### Adding a new page

1. **Create page component in `src/pages/`:**
```typescript
// src/pages/ReportsPage.tsx
export default function ReportsPage() {
  return (
    <div>
      <h1>Reports</h1>
    </div>
  )
}
```

2. **Add route in `src/App.tsx`:**
```typescript
import ReportsPage from './pages/ReportsPage'

<Route path="/reports" element={<ReportsPage />} />
```

### Using the API client

```typescript
import { api } from '@/lib/api'
import { useQuery, useMutation } from '@tanstack/react-query'

function MyComponent() {
  // GET request
  const { data, isLoading } = useQuery({
    queryKey: ['matters'],
    queryFn: () => api.getMatters()
  })

  // POST request
  const mutation = useMutation({
    mutationFn: (data) => api.createMatter(data),
    onSuccess: () => {
      // Handle success
    }
  })

  return <div>...</div>
}
```

### State management

Using Zustand for global state:

```typescript
import { create } from 'zustand'

interface MatterStore {
  selectedMatter: Matter | null
  setSelectedMatter: (matter: Matter) => void
}

export const useMatterStore = create<MatterStore>((set) => ({
  selectedMatter: null,
  setSelectedMatter: (matter) => set({ selectedMatter: matter }),
}))
```

## Testing

### Backend Tests

```bash
cd backend
pytest

# With coverage
pytest --cov=app --cov-report=html

# Run specific test
pytest tests/test_auth.py
```

### Frontend Tests

```bash
cd frontend
npm test

# With coverage
npm test -- --coverage
```

## Code Quality

### Backend

```bash
# Format code
black .

# Lint
ruff check .

# Type checking
mypy .
```

### Frontend

```bash
# Lint
npm run lint

# Type checking
npm run type-check
```

## Environment Variables

### Backend (.env)

```bash
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
SECRET_KEY=your-secret-key

# Optional
OPENAI_API_KEY=sk-...
STORAGE_TYPE=local
ENABLE_AI_EXTRACTION=true
```

### Frontend (.env.local)

```bash
VITE_API_URL=http://localhost:8000
```

## Common Tasks

### Reset database

```bash
# Drop and recreate
dropdb sof_platform
createdb sof_platform
alembic upgrade head
python scripts/create_admin.py
```

### Add new Python dependency

```bash
pip install package-name
pip freeze > requirements.txt
```

### Add new npm package

```bash
npm install package-name
```

### Database backup

```bash
pg_dump -h localhost -U postgres sof_platform > backup.sql
```

### Database restore

```bash
psql -h localhost -U postgres sof_platform < backup.sql
```

## Debugging

### Backend debugging

Add breakpoints with:
```python
import pdb; pdb.set_trace()
```

Or use VS Code debugger with this launch.json:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload"],
      "cwd": "${workspaceFolder}/backend"
    }
  ]
}
```

### Frontend debugging

Use browser DevTools and React DevTools extension.

For Zustand state, install Redux DevTools extension.

## Contributing

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes
3. Run tests
4. Commit: `git commit -m "feat: add new feature"`
5. Push: `git push origin feature/my-feature`
6. Create pull request

## Troubleshooting

### Database connection error
- Check PostgreSQL is running
- Verify DATABASE_URL in .env
- Check firewall settings

### CORS error
- Verify CORS_ORIGINS in backend/.env
- Check frontend API URL configuration

### Port already in use
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Kill process on port 5173
lsof -ti:5173 | xargs kill -9
```

### Docker issues
```bash
# Clean rebuild
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)

## Support

For questions or issues:
- Check documentation
- Review existing issues
- Contact: dev@yourdomain.com
