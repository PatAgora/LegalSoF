# 🚀 Quick Access - Legal SoF Platform

## 🔗 Live Application URLs

### 👉 **[OPEN FRONTEND APPLICATION](https://5175-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai)** 👈
**Login:** `admin@example.com` / `admin123`

---

### 🔧 Backend API
**URL:** https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai

### 📚 API Documentation (Swagger)
**URL:** https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/docs

### ❤️ Health Check
**URL:** https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/health

---

## 🧪 Test the API with curl

### Login and get JWT token:
```bash
curl -X POST https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}'
```

### Get current user (replace TOKEN):
```bash
curl -X GET https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/api/v1/auth/me \
  -H "Authorization: Bearer TOKEN"
```

### Check health:
```bash
curl https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/health
```

---

## 📖 Documentation

- [SANDBOX_DEPLOYMENT.md](./SANDBOX_DEPLOYMENT.md) - Complete sandbox guide
- [README.md](./README.md) - Project overview
- [MVP_SUMMARY.md](./MVP_SUMMARY.md) - MVP features
- [DEVELOPMENT.md](./DEVELOPMENT.md) - Development guide
- [HANDOVER.md](./HANDOVER.md) - Project handover

---

## ✅ Status: FULLY OPERATIONAL

**Last Updated:** 2026-01-09  
**Environment:** GenSpark Sandbox  
**Version:** MVP Foundation v0.1.0

🎉 **Ready to explore!** Click the frontend link above to start.
