# ⚽ Football Predictive Analyzer

Sistema de análisis predictivo de fútbol escalable, basado en la metodología del
**TFG _Análisis Predictivo de la UEFA Champions League 2023_**
(Olalquiaga Muñoz de Dios, ICADE – Universidad Pontificia de Comillas).

---

## 🚀 Inicio rápido

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Lanzar la aplicación
streamlit run app.py
```

Abre tu navegador en `http://localhost:8501`.

---

## 📁 Estructura del proyecto

```
football_predictor/
│
├── app.py                   # Dashboard principal (home)
├── config.py                # Parámetros globales del modelo
├── requirements.txt
├── README.md
│
├── data/
│   ├── __init__.py
│   ├── loader.py            # CRUD: leer/escribir teams.json y players.json
│   ├── teams.json           # Base de datos de equipos (escalable)
│   └── players.json         # Base de datos de jugadores
│
├── predictor/
│   ├── __init__.py
│   ├── poisson_model.py     # Modelo de Poisson (partido, grupo, eliminatoria)
│   ├── player_model.py      # Regresión lineal múltiple (jugadores)
│   └── tournament.py        # Simulación Monte Carlo de torneo
│
└── pages/
    ├── 1_Partido.py         # Análisis de partido individual
    ├── 2_Grupo.py           # Simulador de fase de grupos
    ├── 3_Torneo.py          # Simulador Monte Carlo de torneo
    ├── 4_Jugadores.py       # Predicciones de jugadores
    └── 5_Gestionar_Equipos.py  # CRUD de equipos y jugadores
```

---

## 🧠 Metodología

### 1. Distribución de Poisson (partidos)

```
λ_local    = (ataque_local / media_liga) × (defensa_visitante / media_liga) × media_liga × ventaja_local
λ_visitante = (ataque_visitante / media_liga) × (defensa_local / media_liga) × media_liga

P(home=i, away=j) = Poisson(i, λ_local) × Poisson(j, λ_visitante)
```

Parámetros configurables en `config.py`:
- `LEAGUE_AVG_GOALS = 1.3`
- `HOME_ADVANTAGE = 1.10`
- `MAX_GOALS = 8`

### 2. Regresión lineal múltiple (jugadores)

| Rol | Variables independientes | Variable dependiente |
|-----|--------------------------|----------------------|
| Delantero | disparos totales, disparos a puerta | goles |
| Portero | paradas/p, porterías a 0 | goles encajados/p |
| Defensa | entradas/p, entradas exitosas/p | balones recuperados/p |

### 3. Simulación Monte Carlo (torneo)

Se simulan `N_SIMULATIONS` (por defecto 2 000–10 000) torneos eliminatorios
muestreando goles con `numpy.random.poisson`. La frecuencia de victorias estima
la probabilidad de cada equipo de ganar el torneo.

---

## ➕ Escalar la base de datos

### Añadir un equipo por código

```python
from data.loader import DataLoader

loader = DataLoader()
loader.add_or_update_team({
    "name": "Nuevo Club FC",
    "country": "ESP",
    "league": "La Liga",
    "attack": 1.8,
    "defense": 1.1,
    "ucl_titles": 0,
    "rank": 200,
})
```

### Añadir un jugador por código

```python
loader.add_or_update_player({
    "name": "Nuevo Delantero",
    "team": "Nuevo Club FC",
    "position": "striker",
    "matches_played": 10,
    "goals": 8,
    "shots_attempted": 28,
    "shots_on_target": 14,
    "assists": 2,
}, position="players")
```

O usa directamente la pestaña **⚙️ Gestionar** en la UI.

---

## 🔧 Configuración avanzada

Edita `config.py` para modificar:

```python
LEAGUE_AVG_GOALS = 1.3    # media goles por equipo por partido
HOME_ADVANTAGE   = 1.10   # multiplicador ventaja local
MAX_GOALS        = 8      # máximo goles modelados por equipo
N_SIMULATIONS    = 10_000 # iteraciones Monte Carlo
```

---

## 📦 Dependencias

| Paquete | Uso |
|---------|-----|
| streamlit | Interfaz web interactiva |
| pandas | Manipulación de datos |
| numpy | Álgebra y muestreo aleatorio |
| scipy | `poisson.pmf` |
| scikit-learn | `LinearRegression` |
| plotly | Visualizaciones interactivas |

---

## 📚 Referencias

- Olalquiaga Muñoz de Dios, Í. (2023). *Análisis Predictivo de la UEFA Champions League 2023*. TFG Business Analytics, ICADE.
- Llerena Carrera, R. A. (2025). *Competition data analysis: Using time series analysis techniques to predict competition outcomes*. Retos, 67, 597–606.
- Dixon, M. J., & Coles, S. G. (1997). Modelling association football scores and inefficiencies in the football betting market. *Journal of the Royal Statistical Society*, 46(2), 265–280.
