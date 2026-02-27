# CVP API Deployment Package

Энэхүү package нь CVP API-г өөрийн сервер дээр байрлуулахад шаардлагатай бүх файл, зааварчилгааг агуулна.

## 1. GitHub Repository

**Repository URL**: `https://github.com/ochirbold/sphere-problem`

### Sysadmin-д өгөх зүйлс:

```
1. GitHub repository линк: https://github.com/ochirbold/sphere-problem
2. Branch: main
3. Directory: cvp-sphere-api/
```

### GitHub-аас код татах:

```bash
git clone https://github.com/ochirbold/sphere-problem.git
cd sphere-problem/cvp-sphere-api
```

## 2. Docker Image Build Заавар

### Dockerfile байгаа:

```
cvp-sphere-api/Dockerfile
```

### Docker image бэлдэх:

```bash
# Docker суулгасан байх ёстой
cd cvp-sphere-api
docker build -t cvp-sphere-api:latest .
```

### Build скриптүүд:

- `build-docker.sh` (Linux/Mac)
- `build-docker.bat` (Windows)

## 3. Environment Variables

`.env.example` файлыг `.env` болгон хуулж, дараах утгуудыг тохируулна:

```env
DB_USER=MATH_USER
DB_PASSWORD=Mypswd123$
DB_HOST=172.169.88.80
DB_PORT=1521
DB_SID=DEV
```

**Анхаар**: Бодит нууц үг, хэрэглэгчийн нэрийг ашиглана.

## 4. Docker Container Ажиллуулах

### Энгийн командаар:

```bash
docker run -d \
  --name cvp-api \
  -p 8000:8000 \
  -e DB_USER=your_user \
  -e DB_PASSWORD=your_password \
  -e DB_HOST=your_db_host \
  -e DB_PORT=1521 \
  -e DB_SID=DEV \
  cvp-sphere-api:latest
```

### Docker Compose ашиглах:

`docker-compose.yml` файл үүсгэх:

```yaml
version: "3.8"

services:
  cvp-api:
    image: cvp-sphere-api:latest
    build: .
    container_name: cvp-api
    ports:
      - "8000:8000"
    environment:
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
      - DB_HOST=${DB_HOST}
      - DB_PORT=${DB_PORT}
      - DB_SID=${DB_SID}
    restart: unless-stopped
```

Ажиллуулах:

```bash
docker-compose up -d
```

## 5. Шууд Python Ашиглан (Development)

```bash
# Virtual environment үүсгэх
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Dependencies суулгах
pip install -r requirements.txt

# Environment variables тохируулах
# .env файл үүсгэх эсвэл шууд export хийх

# Server эхлүүлэх
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 6. API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /docs` - API documentation (Swagger UI)
- `GET /redoc` - API documentation (ReDoc)
- `POST /formula/execute` - Formula execution endpoint

## 7. Testing

### Health check:

```bash
curl http://localhost:8000/health
```

### API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 8. Logging

### Docker logs харах:

```bash
docker logs cvp-api
docker logs --tail 100 -f cvp-api
```

### Application logs:

```
cvp-sphere-api/logs/  # директорт хадгалагдана
```

## 9. Monitoring

### Port шалгах:

```bash
netstat -an | grep 8000
# эсвэл
ss -tuln | grep 8000
```

### Process шалгах:

```bash
docker ps | grep cvp-api
```

## 10. Troubleshooting

### 1. Database холболтын алдаа:

```bash
# Connection test
python -c "import oracledb; oracledb.connect(user='\$DB_USER', password='\$DB_PASSWORD', host='\$DB_HOST', port=\$DB_PORT, sid='\$DB_SID')"
```

### 2. Port conflict:

```bash
# Өөр порт ашиглах
docker run -p 8080:8000 cvp-sphere-api:latest
```

### 3. Memory хязгаар:

```bash
docker run -m 512m --memory-swap 1g cvp-sphere-api:latest
```

## 11. Backup ба Restore

### Docker image хадгалах:

```bash
docker save cvp-sphere-api:latest | gzip > cvp-api-backup.tar.gz
```

### Docker image сэргээх:

```bash
docker load < cvp-api-backup.tar.gz
```

## 12. Performance Tuning

### Uvicorn workers:

```bash
# CPU core тоогоор workers тохируулах
docker run -e UVICORN_WORKERS=4 cvp-sphere-api:latest
```

### Database connection pool:

`.env` файлд нэмэх:

```env
ORACLE_POOL_SIZE=10
ORACLE_POOL_INCREMENT=5
ORACLE_POOL_MAX=20
```

## 13. Security Best Practices

### 1. Environment variables:

- `.env` файлыг version control-д оруулахгүй
- Production дээр secrets management system ашиглах

### 2. Network security:

- Firewall тохируулах
- VPN ашиглах
- SSH tunnel ашиглах

### 3. Docker security:

```bash
# Read-only filesystem
docker run --read-only cvp-sphere-api:latest

# Non-root user
docker run --user 1000:1000 cvp-sphere-api:latest
```

## 14. CI/CD Integration

### GitHub Actions:

- `.github/workflows/docker-build.yml` файл байгаа
- Code push үед автоматаар Docker image бэлдэнэ
- GitHub Container Registry дээр хадгална

### Manual trigger:

```bash
gh workflow run docker-build.yml
```

## 15. Contact ба Support

### Холбоо барих:

- Developer: [Таны нэр]
- Email: [Таны email]
- Phone: [Таны утас]

### Issue reporting:

- GitHub Issues: https://github.com/ochirbold/sphere-problem/issues
- Emergency contact: [Яаралтай тусламжийн утас]

## 16. Changelog

### v1.0.0 (2026-02-03)

- Анхны release
- FastAPI суурь
- Oracle DB холболт
- Formula execution API
- Docker support
- GitHub Actions CI/CD

---

**Тэмдэглэл**: Энэхүү package нь production deployment-д бэлэн. Sysadmin нь зөвхөн environment variables (DB_USER, DB_PASSWORD, DB_HOST) тохируулна. Бусад бүх зүйл бэлэн байна.
