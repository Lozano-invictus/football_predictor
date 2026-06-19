# 🚀 QUICKSTART - Sincronización Automática de Datos

## 5 Minutos para tener datos actualizados

### Opción A: Sin API Key (RECOMENDADO PARA EMPEZAR)

```bash
# 1. Ejecutar Streamlit
streamlit run app.py

# 2. Ir a: 🔄 Datos Automáticos (nuevo en sidebar)

# 3. Haz clic en: 📝 Usar datos MOCK

# 4. ¡Listo! Datos de 2024-25 cargados
```

**Ventajas:**
- ✅ Sin configuración
- ✅ Datos de ejemplo reales
- ✅ Inmediato
- ✅ Perfecto para desarrollo

**Limitaciones:**
- ⚠️ Datos estáticos (no se actualizan)
- ⚠️ Solo 5 equipos y 5 goleadores de ejemplo

---

### Opción B: Con API-Football (PRODUCCIÓN)

#### Paso 1: Obtener API Key (Gratis)

1. Ve a: https://rapidapi.com/api-sports/api/api-football
2. Haz clic en **"Subscribe"**
3. Selecciona el plan **"Free"** (2000 requests/mes = ¡Suficiente!)
4. Copia tu **API Key**

![Imagen1](https://img.shields.io/badge/Plan-Gratis-brightgreen)

#### Paso 2: Configurar en la App

```bash
# 1. Ejecutar
streamlit run app.py

# 2. Ir a: 🔄 Datos Automáticos

# 3. En el sidebar izquierdo:
#    - Pestaña "API Key"
#    - Pega tu API key
#    - Haz clic: 🟢 OK

# 4. Selecciona:
#    - "¿Qué deseas actualizar?": "Ambos"
#    - Temporada: 2024

# 5. Haz clic: 🔄 Sincronizar desde API

# 6. ¡Espera 30-60 segundos...
# 7. ✅ Datos sincronizados!
```

**Ventajas:**
- ✅ Datos en tiempo real de Champions League
- ✅ Todos los equipos y jugadores
- ✅ Actualizable cada 24h
- ✅ Estadísticas detalladas

**Limitaciones:**
- ⚠️ Requiere API key
- ⚠️ 2000 requests/mes (suficiente para sincronización diaria)

---

## 📋 Datos Disponibles

### Con MOCK (sin API key)
```
Equipos:
  ✅ Real Madrid (2.8 ataque)
  ✅ Manchester City (2.7 ataque)
  ✅ Barcelona (2.6 ataque)
  ✅ Bayern Munich (2.5 ataque)
  ✅ Liverpool (2.4 ataque)

Goleadores Top 5:
  ✅ Erling Haaland (18 goles)
  ✅ Vinícius Júnior (14 goles)
  ✅ Harry Kane (13 goles)
  ✅ Kylian Mbappé (12 goles)
  ✅ Lautaro Martínez (11 goles)
```

### Con API-Football (completo)
```
✅ 27 equipos de Champions League
✅ 20+ goleadores con estadísticas completas
✅ 10 porteros
✅ 10 defensas
✅ xG (Expected Goals)
✅ Coeficiente UEFA 2025
✅ Ranking doméstico
```

---

## 🔧 Verificar que funciona

```bash
# Test 1: Ver datos cargados
cd football_predictor
python -c "
from data.loader import DataLoader
loader = DataLoader()
teams = loader.load_teams()
print(f'✅ {len(teams)} equipos cargados')
"

# Test 2: Ejecutar scraper demo
python data/scraper.py

# Salida esperada:
# 📊 Football Data Scraper Demo
# ============================================================
# 🏆 Clasificación 2024-25 (mock):
#   Real Madrid: 2.8 goles/p - 0.7 encajados/p
#   ...
# ✅ OK!
```

---

## 📊 Verificar en la UI

### 1. Página Jugadores (👤 Predicción de Rendimiento Individual)

```
Deberías ver:
✅ Ranking de goleadores actualizado
✅ Erling Haaland en el top
✅ Gráfico de predicción vs real
✅ Predicción personalizada funciona
```

### 2. Página Datos Automáticos (🔄)

```
Deberías ver:
✅ Tabla de 27 equipos
✅ Gráficos de Ataque/Defensa
✅ Top 15 goleadores
✅ Opción de sincronizar desde API
```

### 3. Crear una predicción

```
1_Partido.py → Selecciona dos equipos actualizados
Deberías ver:
✅ Probabilidades (1, X, 2)
✅ Expected goals (xG)
✅ Matriz de marcadores
```

---

## 🎯 Casos Comunes

### "Quiero sincronizar automáticamente cada noche"

Edita `config.py`:
```python
SCRAPING_ENABLED = True
SCRAPING_INTERVAL_HOURS = 24

# En producción, usa un job scheduler (Celery)
```

### "Quiero los datos de 2023-24 también"

```bash
# En Streamlit, ve a: 🔄 Datos Automáticos
# Selecciona:
# - Temporada: 2023
# - Haz clic: "🔄 Sincronizar desde API"

# Automatizar en código:
from data.scraper import FootballScraper
scraper = FootballScraper()
scraper.configure_api_key('tu_key')
scraper.sync_data_from_api("UCL", 2023)
```

### "Quiero exportar los datos descargados"

```bash
# En Streamlit: 🔄 Datos Automáticos
# Scroll abajo → "💾 Importar/Exportar Datos"
# Click: "📥 Descargar JSON de equipos"
# Automáticamente: teams_20260502.json
```

### "Tengo error de API key"

```
Problemas comunes:
❌ "API key no configurada"
   → No la pegaste en el sidebar. Intenta de nuevo.

❌ "Error 401 - Unauthorized"
   → La API key es inválida. Cópiala de nuevo.

❌ "Error 429 - Too many requests"
   → Límite de 2000/mes alcanzado. Espera al mes siguiente.

✅ Contacta: https://rapidapi.com/api-sports/api/api-football
```

---

## 💡 Tips

### Para Desarrollo
```python
# Usar datos MOCK es más rápido
# No consumes API requests innecesarios
# Ideal para testing
```

### Para Producción
```python
# Usar API-Football para datos reales
# Configurar sincronización automática
# Monitorear errores de scraping
```

### Para Demostración
```python
# Mezcla ambas opciones:
# 1. Mock data para usuarios nuevos
# 2. API real para datos actuales
# 3. Caché local para velocidad
```

---

## 📈 Próximo Paso: Escalabilidad

Una vez que todo funciona, consulta **ESCALABILIDAD.md** para:
- ✅ Migrar a PostgreSQL
- ✅ Añadir API REST
- ✅ Caché Redis
- ✅ Kubernetes deployment

---

## 🆘 Ayuda

### Logs
```bash
# Ver logs del scraper
tail -f logs/football_predictor.log

# O en la app:
# 🔄 Datos Automáticos → Consola
```

### Test Rápido
```bash
python data/scraper.py          # Demo del scraper
python utils.py                 # Validar entorno
python -m streamlit run app.py  # Ejecutar app
```

### Issues
1. ¿Datos no se actualizan? → Limpia el caché: `rm -rf data/cache/*`
2. ¿Errores de encoding? → Usa Python 3.10+ con UTF-8
3. ¿API lenta? → Espera 30-60 segundos, es normal

---

**¡Listo para usar!** 🎉

Disfruta del Football Predictive Analyzer 2024-25 con datos actualizados en tiempo real.
