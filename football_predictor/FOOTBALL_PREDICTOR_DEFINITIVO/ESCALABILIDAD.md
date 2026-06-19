# 📈 Guía de Escalabilidad - Football Predictor 2024-25

## 🎯 Arquitectura de Escalabilidad

El proyecto está diseñado para crecer progresivamente de un prototipo de escritorio a una plataforma enterprise.

---

## 📊 NIVEL 1: Prototipo Local (ACTUAL)

### Características
- ✅ Datos en JSON local
- ✅ Simulaciones Monte Carlo (10,000 iteraciones)
- ✅ Modelos de ML (Poisson + Regresión Lineal)
- ✅ Interfaz Streamlit

### Rendimiento
- **Usuarios concurrentes**: 1-5
- **Latencia predicción**: < 1 segundo
- **Almacenamiento**: ~10 MB

### Cómo escalar a Nivel 2
```bash
# 1. Añadir sincronización automática
SCRAPING_ENABLED = True
SCRAPING_INTERVAL_HOURS = 24

# 2. Habilitar caché distribuido
CACHE_ENABLED = True
CACHE_BACKEND = "redis"  # próximamente

# 3. Multiprocessing
N_WORKERS = 4
```

---

## 📈 NIVEL 2: Producción (API + Base de Datos)

### Cambios necesarios

#### 2.1 Base de Datos Relacional
```sql
-- Reemplazar JSON con PostgreSQL
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    country VARCHAR(3),
    league VARCHAR(50),
    attack DECIMAL(3,2),
    defense DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    team_id INTEGER REFERENCES teams(id),
    position VARCHAR(20),
    goals INTEGER,
    assists INTEGER,
    shots_attempted INTEGER,
    shots_on_target INTEGER,
    matches_played INTEGER,
    xg DECIMAL(4,2),
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 2.2 API REST
```python
# main.py - FastAPI
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse

app = FastAPI(title="Football Predictor API")

@app.get("/api/v1/predictions/match/{team1}/{team2}")
async def predict_match(team1: str, team2: str):
    # Cachear resultados
    result = await get_prediction(team1, team2)
    return result

@app.post("/api/v1/sync/data")
async def sync_data(background_tasks: BackgroundTasks):
    # Sincronización en background
    background_tasks.add_task(scraper.sync_from_api)
    return {"status": "syncing"}
```

#### 2.3 Caché Redis
```python
# config.py
CACHE_BACKEND = "redis"
REDIS_URL = "redis://localhost:6379"
CACHE_TTL_SECONDS = 1800  # 30 minutos

# utils.py - RedisCacheManager
class RedisCacheManager(CacheManager):
    def __init__(self):
        self.redis = redis.Redis.from_url(REDIS_URL)
    
    def get(self, key):
        return self.redis.get(key)
    
    def set(self, key, value):
        self.redis.setex(key, self.ttl, value)
```

#### 2.4 Sincronización Automática
```python
# jobs/scraper_job.py
from celery import Celery, periodic_task

app = Celery('football_predictor')

@periodic_task.run_every(crontab(hour=0, minute=0))
def sync_daily():
    """Sincroniza datos cada noche a las 00:00"""
    scraper = FootballScraper()
    scraper.sync_data_from_api()
```

### Métricas de Escalabilidad Nivel 2
- **Usuarios concurrentes**: 50-500
- **Latencia predicción**: 100-500 ms
- **Almacenamiento**: 500 MB - 2 GB
- **Requests/segundo**: 100 RPS

---

## 🚀 NIVEL 3: Escala Global (Microservicios)

### Arquitectura
```
┌─────────────────────────────────────────┐
│         API Gateway (Kong/Nginx)        │
└──────┬──────────────────────────┬───────┘
       │                          │
       ▼                          ▼
┌──────────────────┐      ┌──────────────────┐
│ Predictor Service│      │  Data Sync Service│
│ (Port 8001)      │      │  (Port 8002)     │
│ - Poisson        │      │  - API-Football  │
│ - ML Models      │      │  - FotMob        │
│ - Simulations    │      │  - Understat     │
└────────┬─────────┘      └────────┬─────────┘
         │                         │
         └────────────┬────────────┘
                      ▼
            ┌──────────────────────┐
            │  PostgreSQL + Redis  │
            │  (Primary Database)  │
            └──────────────────────┘
```

### Implementación
```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    image: football-predictor-api:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/football
      - REDIS_URL=redis://cache:6379
    depends_on:
      - db
      - cache
  
  scraper:
    image: football-predictor-scraper:latest
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/football
      - API_FOOTBALL_KEY=${API_FOOTBALL_KEY}
    depends_on:
      - db
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=football
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
  
  cache:
    image: redis:7
```

### Rendimiento Nivel 3
- **Usuarios concurrentes**: 5,000+
- **Latencia predicción**: 50-100 ms
- **Almacenamiento**: 10 GB+
- **Requests/segundo**: 1,000+ RPS
- **Disponibilidad**: 99.9%

---

## 🧠 Estrategias de Optimización

### 1. Modelos de ML Avanzados
```python
# Deep Learning para predicciones
import tensorflow as tf
from tensorflow import keras

# Modelo LSTM para series temporales
model = keras.Sequential([
    keras.layers.LSTM(64, input_shape=(10, 5)),  # 10 partidos, 5 features
    keras.layers.Dense(32, activation='relu'),
    keras.layers.Dropout(0.5),
    keras.layers.Dense(1, activation='sigmoid')  # Probabilidad resultado
])

# Entrenar con histórico de múltiples temporadas
history = model.fit(X_train, y_train, epochs=100, batch_size=32)
```

### 2. Compresión de Datos
```python
# Reducir tamaño JSON
from zlib import compress, decompress

compressed = compress(json_data.encode())
ratio = len(compressed) / len(json_data)  # ~30% de tamaño original
```

### 3. Consultas SQL Optimizadas
```sql
-- Índices para acelerar búsquedas
CREATE INDEX idx_team_attack ON teams(attack);
CREATE INDEX idx_player_goals ON players(goals DESC);
CREATE INDEX idx_player_team ON players(team_id);

-- Queries optimizadas
SELECT name, goals FROM players 
WHERE position = 'striker' 
ORDER BY goals DESC 
LIMIT 20;  -- Consulta < 10ms con índice
```

### 4. Paralelización
```python
# Ejecutar simulaciones en paralelo
from multiprocessing import Pool

def simulate_tournament(teams):
    return run_monte_carlo(teams, n_simulations=10000)

with Pool(processes=4) as pool:
    results = pool.map(simulate_tournament, team_groups)
```

---

## 📊 Monitoreo y Alertas

### Métricas Clave
```python
# config.py - Feature flag para monitoreo
MONITORING_ENABLED = True

# Métricas a trackear:
# - Tiempo de respuesta por endpoint
# - Errores de scraping
# - Hit rate del caché
# - Uso de memoria/CPU
# - Errores de predicción (vs histórico)

# Tools: Prometheus, Grafana, DataDog
```

### Logs Centralizados
```python
# ELK Stack (Elasticsearch, Logstash, Kibana)
import logging
from pythonjsonlogger import jsonlogger

logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
```

---

## 🔐 Seguridad en Escalabilidad

### 1. API Key Management
```python
# Usar Vault o AWS Secrets Manager
import hvac

client = hvac.Client(url='http://vault:8200')
secret = client.secrets.kv.read_secret_version(path='football-predictor/api-key')
API_KEY = secret['data']['data']['key']
```

### 2. Rate Limiting
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()

@app.get("/api/predictions")
@limiter.limit("100/minute")
async def get_predictions(request: Request):
    pass
```

### 3. Autenticación
```python
from fastapi.security import HTTPBearer, HTTPAuthCredential

security = HTTPBearer()

@app.get("/api/predictions")
async def get_predictions(credentials: HTTPAuthCredential = Depends(security)):
    token = credentials.credentials
    # Validar JWT token
    return predictions
```

---

## 💾 Migración de Datos: JSON → PostgreSQL

```python
# migration.py
import json
import psycopg2

def migrate_to_postgresql():
    # Leer JSON
    with open('data/teams.json') as f:
        teams_data = json.load(f)
    
    # Conectar a PostgreSQL
    conn = psycopg2.connect("dbname=football user=postgres")
    cur = conn.cursor()
    
    # Insertar datos
    for team in teams_data['teams']:
        cur.execute("""
            INSERT INTO teams (name, country, league, attack, defense)
            VALUES (%s, %s, %s, %s, %s)
        """, (team['name'], team['country'], team['league'], 
              team['attack'], team['defense']))
    
    conn.commit()
    cur.close()
    conn.close()

# Ejecutar: python migration.py
```

---

## 🎯 Roadmap de Escalabilidad

### Q3 2026 (Nivel 1 → 2)
- [ ] PostgreSQL migration
- [ ] Redis caché
- [ ] FastAPI backend
- [ ] Documentación OpenAPI

### Q4 2026 (Nivel 2 → 3)
- [ ] Kubernetes deployment
- [ ] Prometheus + Grafana
- [ ] ELK Stack logging
- [ ] Multi-region support

### 2027 (Nivel 3+)
- [ ] Deep Learning models (LSTM, Transformers)
- [ ] Real-time data streaming (Kafka)
- [ ] Global CDN (CloudFlare)
- [ ] Machine learning pipeline (MLflow)

---

## 📞 Soporte

Para preguntas sobre escalabilidad:
1. Consulta la documentación en cada nivel
2. Abre un issue en GitHub
3. Contacta al equipo de desarrollo

---

**Última actualización**: Mayo 2026
**Versión**: 2.0
