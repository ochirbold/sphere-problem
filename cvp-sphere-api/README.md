# CVP Sphere API - Formula Runtime and Database Calculator

**Байршил:** Энэ README.md файл одоо `cvp-sphere-api/` хавтасанд байрладаг. Formula файлууд `cvp-sphere-api/formula/` хавтасанд байна.

Энэхүү repository нь математик томьёог аюулгүйгээр үнэлж, мэдээллийн сангийн бичлэгүүдэд хэрэглэх хэрэгслүүдийг агуулдаг. FastAPI суурьтай CVP (Cost-Volume-Profit) Optimization & Formula Engine API-г багтаасан.

## Монгол хэлээр заавар

### Багийн гишүүдэд зориулсан заавар

#### 1. Virtual Environment ашиглах

**Анхаар:** Төсөлд `cvp-sphere-api/venv/` фолдер байгаа бөгөөд энэ нь шаардлагатай бүх Python сангуудыг агуулдаг. Хэрэв та шинээр суулгахыг хүсвэл:

```bash
# cvp-sphere-api хавтас руу орж
cd cvp-sphere-api

# Virtual environment үүсгэх (хэрэв байхгүй бол)
python -m venv venv

# Virtual environment идэвхжүүлэх
# Windows (Command Prompt):
venv\Scripts\activate
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/Mac:
source venv/bin/activate

# Шаардлагатай сангууд суулгах
pip install -r requirements.txt
```

**Анхаар:** Хэрэв та virtual environment ашиглахгүй бол системийн Python ашиглана. Гэхдээ virtual environment ашиглах нь илүү аюулгүй бөгөөд төслүүдийн хооронд сангуудын зөрчилдөөнөөс сэргийлнэ.

#### 2. Кодоо татаж авах (Pull хийх)

**Эхний удаа кодоо татаж авах:**

```bash
# GitHub repository-г clone хийх
git clone https://github.com/ochirbold/sphere-problem.git
cd sphere-problem
```

**Аль хэдийн clone хийсэн бол шинэчлэлт татаж авах:**

```bash
# Одоогийн branch дээрээ байгаа эсэхийг шалгах
git checkout main

# GitHub-с шинэчлэлтүүдийг татаж авах
git pull origin main
```

#### 3. Мэдээллийн сан холболтыг тохируулах

**Анхаар:** Кодонд нууц мэдээлэл байхгүй. Та өөрийн мэдээллийн сангийн нууц үгээ тохируулах шаардлагатай.

**Алхам алхмаар заавар:**

1. **Жишээ тохиргооны файл үүсгэх:**

   ```bash
   cd cvp-sphere-api/formula
   cp .env.example .env
   ```

2. **.env файлыг засах:**

   ```bash
   # Текст редактор ашиглан .env файлыг нээх
   # Дараах утгуудыг өөрчлөх:

   # Мэдээллийн сангийн хэрэглэгчийн нэр
   DB_USER=МЭДЭЭЛЛИЙН_САНГИЙН_ХЭРЭГЛЭГЧ

   # Мэдээллийн сангийн нууц үг
   DB_PASSWORD=НУУЦ_ҮГ

   # Бусад утгуудыг шаардлагатай бол өөрчлөх
   # DB_HOST, DB_PORT, DB_SID
   ```

3. **Орчны хувьсагч тохируулах:**

   **Windows (PowerShell):**

   ```powershell
   # .env файлаас орчны хувьсагч унших
   Get-Content .env | ForEach-Object {
       if ($_ -match '^\s*([^#][^=]+)=(.*)') {
           [Environment]::SetEnvironmentVariable($matches[1], $matches[2])
       }
   }
   ```

   **Linux/Mac:**

   ```bash
   # .env файлаас орчны хувьсагч унших
   export $(grep -v '^#' .env | xargs)
   ```

#### 4. Pythoncode.py скрипт ажиллуулах

**Шаардлагатай сангууд суулгах:**

```bash
# cvp-sphere-api хавтас руу орж
cd cvp-sphere-api

# Шаардлагатай сангууд суулгах
pip install -r requirements.txt

# Эсвэл ганц сангууд суулгах
pip install oracledb python-dotenv
```

**Скрипт ажиллуулах:**

**Анхаар:** Одоо скрипт `.env` файлаас автоматаар мэдээллийн сангийн холболтын мэдээллийг уншина. Тиймээс орчны хувьсагч тохируулах шаардлагагүй.

````bash
# cvp-sphere-api/formula хавтас руу орж
cd cvp-sphere-api/formula

# Скрипт ажиллуулах
python PYTHONCODE.py ...

```bash
# Ерөнхий хэлбэр:
python PYTHONCODE.py <хүснэгтийн_нэр> <id_багана> <ТОМЬЁО> [ТОМЬЁО ...] '"багана1":багана1 "багана2":багана2'

# Жишээ (req файлд байгаа командыг ашиглах):
python PYTHONCODE.py VT_DATA.V_17687947217601 ID 'CM_J:P_J - C_J' 'X0_J:(X_MIN_J + X_MAX_J) / 2' 'R:(X_MAX_J - X_MIN_J) / 2' 'SAFE_X_MIN:X0_J - R' 'SAFE_X_MAX:X0_J + R' '"P_J":P_J "C_J":C_J "X_MIN_J":X_MIN_J "X_MAX_J":X_MAX_J "F":F "CM_J":CM_J "X0_J":X0_J "R":R "SAFE_X_MIN":SAFE_X_MIN "SAFE_X_MAX":SAFE_X_MAX'
````

**Алдаа гарвал:**

- `DB_USER`, `DB_PASSWORD` орчны хувьсагч тохируулсан эсэхийг шалгах
- Мэдээллийн сантай холбогдох эрх шалгах
- Хүснэгт, багануудын нэр зөв эсэхийг шалгах

#### 5. Хамтын ажиллагаа

**Өөрчлөлт оруулах:**

```bash
# Шинэ branch үүсгэх
git checkout -b шинэ-функциональ

# Өөрчлөлтүүд хийх
# Файлуудыг засах

# Өөрчлөлтүүдээ нэмэх
git add .

# Commit хийх
git commit -m "Өөрчлөлтийн тайлбар"

# GitHub руу push хийх
git push origin шинэ-функциональ

# GitHub дээр Pull Request үүсгэх
```

---

## FastAPI CVP Optimization & Formula Engine API

**Version:** 2.0.0

Энэхүү API нь CVP (Cost-Volume-Profit) анализ хийх, математик томьёог аюулгүйгээр үнэлэх, мэдээллийн сангийн бичлэгүүдэд томьёог хэрэглэх боломжийг олгодог.

### API Ажиллуулах

#### Development Mode (Хөгжүүлэлтийн горим):

```bash
# cvp-sphere-api хавтас руу орж
cd cvp-sphere-api

# Virtual environment идэвхжүүлэх (хэрэв байгаа бол)
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# FastAPI серверийг ажиллуулах
uvicorn main:app --reload --port 8000
```

#### Production Mode (Үйлдвэрийн горим):

```bash
# start.sh скрипт ашиглах
./start.sh

# Эсвэл шууд командаар
uvicorn main:app --host 0.0.0.0 --port 8000
```

#### API Documentation:

API нь автоматаар Swagger болон ReDoc documentation үүсгэдэг:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **API Root:** http://localhost:8000/

### Docker Ашиглах

#### Docker Image Бэлдэх:

```bash
# cvp-sphere-api хавтас руу орж
cd cvp-sphere-api

# Docker image бэлдэх
docker build -t cvp-sphere-api .

# Image шалгах
docker images | grep cvp-sphere-api
```

#### Docker Container Ажиллуулах:

```bash
# Container ажиллуулах
docker run -p 8000:8000 cvp-sphere-api

# Environment variables тохируулахтай ажиллуулах
docker run -p 8000:8000 -e DB_USER=your_user -e DB_PASSWORD=your_password cvp-sphere-api

# .env файл ашиглах
docker run -p 8000:8000 --env-file formula/.env cvp-sphere-api
```

#### Docker Compose Ашиглах (хэрэгтэй бол):

`docker-compose.yml` файл үүсгэх:

```yaml
version: "3.8"
services:
  cvp-sphere-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
      - DB_HOST=${DB_HOST}
      - DB_PORT=${DB_PORT}
      - DB_SID=${DB_SID}
    volumes:
      - ./logs:/app/logs
```

### Railway Deployment

#### Railway CLI Суулгах:

```bash
# Railway CLI суулгах
npm install -g @railway/cli

# Railway руу нэвтрэх
railway login
```

#### Railway Проект Үүсгэх:

```bash
# Railway проект үүсгэх
railway init

# Environment variables тохируулах
railway variables set DB_USER your_username
railway variables set DB_PASSWORD your_password
railway variables set DB_HOST 172.169.88.80
railway variables set DB_PORT 1521
railway variables set DB_SID DEV

# Deploy хийх
railway up
```

#### Railway Dashboard Ашиглах:

1. https://railway.app руу нэвтрэх
2. "New Project" дарж шинэ проект үүсгэх
3. "Deploy from GitHub repo" сонгох
4. `ochirbold/sphere-problem` repository сонгох
5. `cvp-sphere-api` хавтасыг root болгох
6. Environment variables тохируулах
7. Deploy хийх

### API Endpoints

#### 1. CVP Optimization (`POST /optimize`)

CVP анализ хийх (volume, price, cost, robust case):

```bash
curl -X POST "http://localhost:8000/optimize" \
  -H "Content-Type: application/json" \
  -d '{
    "case": "volume",
    "fixedCost": "10000",
    "products": [
      {
        "itemName": "Product A",
        "itemCode": "PA001",
        "p": "150",
        "c": "100",
        "xmin": "50",
        "xmax": "200"
      }
    ]
  }'
```

#### 2. Formula Calculation (`POST /formula/calculate`)

Мэдээллийн сангаас өгөгдөл уншиж томьёог тооцоолох:

```bash
curl -X POST "http://localhost:8000/formula/calculate" \
  -H "Content-Type: application/json" \
  -d '{
    "indicator_id": 17687947217601,
    "id_column": "ID",
    "formulas": [
      "CM_J:P_J - C_J",
      "X0_J:(X_MIN_J + X_MAX_J) / 2"
    ]
  }'
```

#### 3. Direct Formula Calculation (`POST /formula/calculate/direct`)

Мэдээллийн сангүйгээр шууд тооцоолох:

```bash
curl -X POST "http://localhost:8000/formula/calculate/direct" \
  -H "Content-Type: application/json" \
  -d '{
    "table_name": "VT_DATA",
    "id_column": "ID",
    "formulas": {
      "CM_J": "P_J - C_J",
      "X0_J": "(X_MIN_J + X_MAX_J) / 2"
    },
    "data": [
      {
        "ID": 1,
        "P_J": 150,
        "C_J": 100,
        "X_MIN_J": 50,
        "X_MAX_J": 200
      }
    ]
  }'
```

#### 4. Health Checks:

```bash
# System health check
curl "http://localhost:8000/health"

# Formula engine health check
curl "http://localhost:8000/formula/health"
```

### Environment Variables

API ажиллуулахын тулд дараах environment variables тохируулах шаардлагатай:

#### Database Connection:

```bash
DB_USER=your_username           # Мэдээллийн сангийн хэрэглэгчийн нэр
DB_PASSWORD=your_password       # Мэдээллийн сангийн нууц үг
DB_HOST=172.169.88.80           # Мэдээллийн сангийн хаяг
DB_PORT=1521                    # Мэдээллийн сангийн порт
DB_SID=DEV                      # Мэдээллийн сангийн SID
```

#### API Configuration:

```bash
PORT=8000                       # API серверийн порт
PYTHONPATH=/app                 # Python path
PYTHONUNBUFFERED=1              # Python unbuffered output
```

#### Development Configuration:

```bash
# Development mode (auto-reload)
UVICORN_RELOAD=true

# Log level
LOG_LEVEL=info
```

### Files

#### 1. formula_runtime.py

A secure formula evaluator using Python's AST (Abstract Syntax Tree) for safe expression evaluation.

**Features:**

- Safe evaluation of mathematical expressions
- Only allowed functions and operators are permitted
- AST caching for performance
- Extracts identifiers from expressions

**Allowed Functions:**

- Basic math: `pow`, `sqrt`, `abs`, `min`, `max`
- Array operations: `SUM`, `AVG`, `DOT`, `NORM`, `COUNT`

#### 2. PYTHONCODE.PY

A script to read data from Oracle database, apply formulas, and update the database with results.

**Features:**

- Dependency analysis and topological sorting of formulas
- Batch updates for performance
- Automatic numeric type conversion
- Error logging and continuation on errors

**Usage:**

```bash
python PYTHONCODE.py <table> <id_column> <TARGET:EXPR> [TARGET:EXPR ...] '"col1":col1 "col2":col2'
```

#### 3. req

Example command showing how to use the script with specific formulas.

### Security Note

**Important:** The `PYTHONCODE.PY` file now reads database credentials from environment variables for security. No hardcoded credentials are present in the code.

**Setup Instructions:**

1. **Copy the example environment file:**

   ```bash
   cp .env.example .env
   ```

2. **Edit the `.env` file**
