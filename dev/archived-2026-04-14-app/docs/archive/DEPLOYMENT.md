# Legal SoF Platform - Deployment Guide

## Production Deployment

### Prerequisites
- Docker & Docker Compose
- PostgreSQL 15+ (managed service recommended)
- Domain name with SSL certificate
- S3-compatible object storage (AWS S3, MinIO, etc.)
- OpenAI API key (for AI features)

### Environment Configuration

Create a `.env` file in the backend directory with production values:

```bash
# Environment
ENVIRONMENT=production
DEBUG=False

# Database (use managed PostgreSQL)
DATABASE_URL=postgresql+asyncpg://user:password@db-host:5432/sof_platform

# Security (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
SECRET_KEY=your-production-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=480  # 8 hours
REFRESH_TOKEN_EXPIRE_MINUTES=10080  # 7 days

# CORS (your production domains)
CORS_ORIGINS=["https://yourdomain.com","https://app.yourdomain.com"]

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Storage (S3)
STORAGE_TYPE=s3
S3_BUCKET=your-bucket-name
S3_REGION=us-east-1
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key

# Observability
LOG_LEVEL=INFO
SENTRY_DSN=your-sentry-dsn  # Optional

# Feature Flags
ENABLE_AI_EXTRACTION=true
ENABLE_AI_NARRATIVE=true
```

### AWS Deployment

#### Option 1: ECS Fargate (Recommended)

1. **Build and push Docker images:**

```bash
# Backend
docker build -f docker/Dockerfile.backend -t sof-backend:latest .
docker tag sof-backend:latest <your-ecr-repo>/sof-backend:latest
docker push <your-ecr-repo>/sof-backend:latest

# Frontend
docker build -f docker/Dockerfile.frontend -t sof-frontend:latest .
docker tag sof-frontend:latest <your-ecr-repo>/sof-frontend:latest
docker push <your-ecr-repo>/sof-frontend:latest
```

2. **Create RDS PostgreSQL instance:**
   - Engine: PostgreSQL 15+
   - Instance class: db.t3.medium (minimum)
   - Storage: 100GB SSD
   - Enable automated backups
   - Enable encryption at rest

3. **Create S3 bucket:**
   - Enable versioning
   - Enable server-side encryption
   - Configure CORS policy
   - Set up lifecycle rules for old documents

4. **Deploy to ECS:**
   - Create ECS cluster
   - Define task definitions for backend and frontend
   - Configure Application Load Balancer
   - Set up auto-scaling policies
   - Configure CloudWatch logs

5. **Run database migrations:**

```bash
# SSH into ECS task or use ECS Exec
alembic upgrade head
python scripts/create_admin.py
```

#### Option 2: EC2 with Docker Compose

1. **Launch EC2 instance:**
   - Ubuntu 22.04 LTS
   - t3.medium or larger
   - Attach security groups (80, 443, 22)

2. **Install dependencies:**

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose nginx certbot python3-certbot-nginx
sudo usermod -aG docker $USER
```

3. **Clone and configure:**

```bash
git clone <your-repo>
cd sof-platform
cp backend/.env.example backend/.env
# Edit backend/.env with production values
```

4. **Deploy:**

```bash
docker-compose -f docker-compose.prod.yml up -d
```

5. **Configure Nginx reverse proxy:**

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

6. **Setup SSL:**

```bash
sudo certbot --nginx -d yourdomain.com
```

### Azure Deployment

1. **Azure Container Instances or App Service:**
   - Similar to AWS ECS approach
   - Use Azure Database for PostgreSQL
   - Use Azure Blob Storage instead of S3

2. **Azure DevOps Pipeline:**

```yaml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

steps:
- task: Docker@2
  inputs:
    command: buildAndPush
    repository: sof-backend
    dockerfile: docker/Dockerfile.backend
    
- task: AzureWebAppContainer@1
  inputs:
    azureSubscription: '<subscription>'
    appName: 'sof-platform'
    containers: '<registry>/sof-backend:latest'
```

### Database Migration Strategy

```bash
# Backup before migration
pg_dump -h localhost -U postgres sof_platform > backup.sql

# Run migrations
docker-compose exec backend alembic upgrade head

# Rollback if needed
docker-compose exec backend alembic downgrade -1
```

### Monitoring & Observability

1. **Application Monitoring:**
   - Sentry for error tracking
   - CloudWatch / Azure Monitor for logs
   - Prometheus + Grafana for metrics

2. **Database Monitoring:**
   - RDS Performance Insights
   - Query performance monitoring
   - Connection pooling metrics

3. **Health Checks:**
   - `/health` endpoint for liveness
   - Database connection check
   - Storage accessibility check

### Backup Strategy

1. **Database:**
   - Automated RDS snapshots (daily)
   - Point-in-time recovery enabled
   - Cross-region replication for DR

2. **Documents:**
   - S3 versioning enabled
   - Cross-region replication
   - Lifecycle policy for archives

3. **Application State:**
   - Daily backups of configuration
   - Infrastructure as Code (Terraform/CloudFormation)

### Security Checklist

- [ ] Enable HTTPS only (HSTS headers)
- [ ] Rotate SECRET_KEY regularly
- [ ] Use IAM roles instead of access keys
- [ ] Enable VPC security groups
- [ ] Regular security updates
- [ ] WAF rules for API protection
- [ ] Rate limiting enabled
- [ ] Audit logging to separate storage
- [ ] Encryption at rest for database
- [ ] Encryption in transit (TLS 1.3)
- [ ] Regular penetration testing
- [ ] GDPR/data protection compliance

### Scaling Considerations

1. **Horizontal Scaling:**
   - Multiple backend instances behind ALB
   - Stateless application design
   - Session storage in database or Redis

2. **Database Scaling:**
   - Read replicas for queries
   - Connection pooling (pgbouncer)
   - Partitioning for large tables

3. **Storage Scaling:**
   - S3 auto-scales
   - CDN for static assets
   - Document processing queue

### Cost Optimization

1. **Compute:**
   - Use reserved instances for predictable load
   - Auto-scaling for variable load
   - Spot instances for background jobs

2. **Storage:**
   - S3 Intelligent-Tiering
   - Lifecycle policies for old documents
   - Compression for archives

3. **Database:**
   - Right-size RDS instance
   - Aurora Serverless for variable workloads
   - Regular vacuum and analyze

### Disaster Recovery

1. **RTO (Recovery Time Objective):** 4 hours
2. **RPO (Recovery Point Objective):** 15 minutes

**DR Procedure:**
1. Restore RDS from latest snapshot
2. Update DNS to failover region
3. Restore S3 from replication
4. Deploy application from container registry
5. Verify all services operational

### Support & Maintenance

- Regular security patches (monthly)
- Dependency updates (quarterly)
- Database maintenance windows
- Backup verification (monthly)
- Disaster recovery drills (quarterly)

---

For questions or issues, contact: support@yourdomain.com
