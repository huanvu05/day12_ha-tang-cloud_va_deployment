#  Delivery Checklist — Day 12 Lab Submission

> **Student Name:** Vũ Văn Huân
> **Student ID:** 2A202600348
> **Date:** 17/04/2026

---

##  Submission Requirements

Submit a **GitHub repository** containing:

# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
1. Hardcoded API keys trong code → dễ lộ secrets
2. Không có authentication → ai cũng gọi được API
3. Không có rate limiting → dễ bị spam / tốn chi phí
4. Không có health check → cloud không biết khi nào restart
5. Không có logging chuẩn → khó debug production
6. Không có graceful shutdown → mất request khi tắt server
7. Lưu state trong memory → không scale được

---

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why Important? |
|---------|--------|------------|----------------|
| Config | Hardcoded | Env variables | Tránh lộ secrets, dễ thay đổi |
| Auth | Không có | API key / JWT | Bảo vệ API |
| Rate limit | Không có | Có giới hạn | Tránh abuse |
| Logging | print() | structured logging | Debug dễ |
| Health check | ❌ | ✅ | Monitoring & auto-restart |
| Shutdown | Đột ngột | Graceful | Không mất request |
| State | In-memory | Redis | Scale được nhiều instance |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. Base image: `python:3.11-slim`
2. Working directory: `/app`
3. Copy requirements trước để cache layer → build nhanh hơn
4. CMD vs ENTRYPOINT:
   - CMD: có thể override
   - ENTRYPOINT: cố định

---

### Exercise 2.3: Image size comparison
- Develop: ~800 MB  
- Production: ~250 MB  
- Difference: ~68% giảm

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment
- URL: https://your-app.railway.app
- Screenshot: screenshots/deploy.png

---

## Part 4: API Security

### Exercise 4.1-4.3: Test results

**Test API key:**

```bash
# Không có key
curl http://localhost:8000/ask
# → 401 Unauthorized

# Có key
curl -H "X-API-Key: secret-key" http://localhost:8000/ask
# → 200 OK
Test JWT:

# Lấy token
curl http://localhost:8000/auth/token \
  -X POST -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"secret"}'

# Gọi API
curl -H "Authorization: Bearer <token>" http://localhost:8000/ask \
  -X POST -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
# → 200 OK
---
Test rate limiting:

for i in {1..20}; do
  curl http://localhost:8000/ask \
    -X POST \
    -H "Authorization: Bearer <token>" \
    -H "Content-Type: application/json" \
    -d '{"question": "test"}'
done
# → Sau giới hạn: 429 Too Many Requests

Exercise 4.4: Cost guard implementation

Cách tiếp cận:

Track usage theo user bằng Redis hoặc in-memory (demo)
Mỗi request:
Ước lượng token input/output
Tính cost theo pricing model
Nếu vượt budget:
→ return HTTP 402

Logic chính:

Mỗi user có budget/ngày hoặc tháng
Lưu usage theo key:
budget:{user_id}:{date}
Reset theo thời gian bằng expire
Part 5: Scaling & Reliability
Exercise 5.1: Health & Ready
/health: luôn trả 200 nếu app còn sống
/ready: check:
app đã init xong chưa
dependencies (Redis nếu có)
Exercise 5.2: Graceful shutdown
Sử dụng signal SIGTERM
Khi shutdown:
Ngừng nhận request mới
Đợi request đang chạy hoàn thành
Đóng resource
Dùng lifespan trong FastAPI để xử lý
Exercise 5.3: Stateless design
Không lưu state trong memory
Dữ liệu phải đưa ra ngoài:
Redis (cache, session, rate limit)
Giúp scale nhiều instance
Exercise 5.4: Load balancing
Sử dụng nhiều instance (docker compose / cloud)
Load balancer phân phối request
Nếu 1 instance chết → hệ thống vẫn hoạt động
Exercise 5.5: Testing
Test health check:
curl http://localhost:8000/health
Test readiness:
curl http://localhost:8000/ready
Test graceful shutdown:
python app.py &
PID=$!
kill -TERM $PID
Quan sát:
Server không chết ngay
Đợi request xử lý xong
Log hiển thị shutdown an toàn

### 2. Full Source Code - Lab 06 Complete (60 points)

Your final production-ready agent with all files:

```
your-repo/
├── app/
│   ├── main.py              # Main application
│   ├── config.py            # Configuration
│   ├── auth.py              # Authentication
│   ├── rate_limiter.py      # Rate limiting
│   └── cost_guard.py        # Cost protection
├── utils/
│   └── mock_llm.py          # Mock LLM (provided)
├── Dockerfile               # Multi-stage build
├── docker-compose.yml       # Full stack
├── requirements.txt         # Dependencies
├── .env.example             # Environment template
├── .dockerignore            # Docker ignore
├── railway.toml             # Railway config (or render.yaml)
└── README.md                # Setup instructions
```

**Requirements:**
-  All code runs without errors
-  Multi-stage Dockerfile (image < 500 MB)
-  API key authentication
-  Rate limiting (10 req/min)
-  Cost guard ($10/month)
-  Health + readiness checks
-  Graceful shutdown
-  Stateless design (Redis)
-  No hardcoded secrets

---

### 3. Service Domain Link

Create a file `DEPLOYMENT.md` with your deployed service information:

```markdown
# Deployment Information

## Public URL
https://zero6-lab.onrender.com/

## Platform
Render

## Test Commands

### Health Check
```bash
curl https://zero6-lab.onrender.com/health
# Expected: {"status": "ok"}
```

### API Test (with authentication)
```bash
curl -X POST https://zero6-lab.onrender.com/ask \
  -H "X-API-Key: huanvu05" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
```

## Environment Variables Set
- PORT
- REDIS_URL
- AGENT_API_KEY
- LOG_LEVEL
- MONTHLY_BUDGET_USD
- RATE_LIMIT_PER_MINUTE
- RATE_LIMIT_WINDOW_SECONDS
- ALLOWED_ORIGINS
- APP_VERSION
- ENVIRONMENT

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
![alt text](<Screenshot 2026-04-18 at 12.28.02.png>) ![alt text](<Screenshot 2026-04-18 at 12.27.45.png>)


##  Pre-Submission Checklist

- [ ] Repository is public (or instructor has access)
- [ ] `MISSION_ANSWERS.md` completed with all exercises
- [ ] `DEPLOYMENT.md` has working public URL
- [ ] All source code in `app/` directory
- [ ] `README.md` has clear setup instructions
- [ ] No `.env` file committed (only `.env.example`)
- [ ] No hardcoded secrets in code
- [ ] Public URL is accessible and working
- [ ] Screenshots included in `screenshots/` folder
- [ ] Repository has clear commit history

---

##  Self-Test

Before submitting, verify your deployment:

```bash
# 1. Health check
curl https://zero6-lab.onrender.com/health
{"status":"degraded","version":"1.0.0","environment":"development","redis":"disconnected","uptime_seconds":151.5,"total_requests":5,"active_requests":1,"timestamp":"2026-04-18T05:26:06.101020+00:00"}% 

# 2. Authentication required
curl https://zero6-lab.onrender.com/ask
# Should return 401
{"error":"authentication_error","detail":"Missing API key. Include header: X-API-Key: <your-key>"}%

# 3. With API key works
curl -H "X-API-Key: huanvu05" https://your-app.railway.app/ask \
  -X POST -d '{"user_id":"test","question":"Hello"}'
# Should return 200

# 4. Rate limiting
for i in {1..15}; do 
  curl -H "X-API-Key: huanvu05" https://your-app.railway.app/ask \
    -X POST -d '{"user_id":"test","question":"test"}'; 
done
# Should eventually return 429
```

---

##  Submission

**Submit your GitHub repository URL:**

```
https://github.com/huanvu05/day12_ha-tang-cloud_va_deployment.git```

**Deadline:** 17/4/2026

---

##  Quick Tips

1.  Test your public URL from a different device
2.  Make sure repository is public or instructor has access
3.  Include screenshots of working deployment
4.  Write clear commit messages
5.  Test all commands in DEPLOYMENT.md work
6.  No secrets in code or commit history

---

##  Need Help?

- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review [CODE_LAB.md](CODE_LAB.md)
- Ask in office hours
- Post in discussion forum

---