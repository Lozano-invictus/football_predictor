# 🚀 Guía de despliegue en Streamlit Cloud

Sigue estos pasos para tener la app disponible en internet **gratis**,
sin instalar nada en tu PC.

---

## Paso 1 — Crear cuenta en GitHub (si no tienes)

Ve a [github.com](https://github.com) → Sign up (es gratis).

---

## Paso 2 — Subir el proyecto a GitHub

### Opción A: Desde la web de GitHub (más fácil)

1. Entra a GitHub → botón verde **"New"** (nuevo repositorio)
2. Ponle nombre: `football-predictor`
3. Marca **Public** (necesario para Streamlit Cloud gratuito)
4. Clic en **"Create repository"**
5. En la página del repositorio → **"uploading an existing file"**
6. Arrastra **todos los archivos** de la carpeta `football_predictor/`
   (incluyendo las subcarpetas `data/`, `predictor/`, `pages/`, `.streamlit/`)
   > ⚠️ NO subas el archivo `.streamlit/secrets.toml`
7. Clic en **"Commit changes"**

### Opción B: Desde terminal con Git

```bash
cd football_predictor
git init
git add .
git commit -m "primer commit"
git remote add origin https://github.com/TU_USUARIO/football-predictor.git
git push -u origin main
```

---

## Paso 3 — Crear cuenta en Streamlit Cloud

Ve a [share.streamlit.io](https://share.streamlit.io) → **"Sign up"** con tu cuenta de GitHub.

---

## Paso 4 — Desplegar la app

1. En Streamlit Cloud → **"New app"**
2. Selecciona tu repositorio: `TU_USUARIO/football-predictor`
3. Branch: `main`
4. Main file path: `app.py`
5. Clic en **"Deploy!"**

Streamlit instalará las dependencias del `requirements.txt` automáticamente.
En 2-3 minutos tendrás tu app en una URL como:
`https://tu-usuario-football-predictor.streamlit.app`

---

## Paso 5 — Configurar la API key (para actualización de datos)

En Streamlit Cloud, **no puedes subir secrets.toml** por seguridad.
En su lugar:

1. Ve a tu app → **"⋮"** (tres puntos) → **"Settings"**
2. Pestaña **"Secrets"**
3. Pega esto y reemplaza con tu key real:

```toml
FOOTBALL_DATA_KEY = "TU_API_KEY_DE_FOOTBALL_DATA_ORG"
```

4. Clic en **"Save"** → la app se reinicia automáticamente

---

## Paso 6 — Actualizar datos

Una vez desplegada, ve a la pestaña **🔄 Actualizar Datos** en la app.
El sistema leerá la API key que configuraste en Secrets automáticamente.

---

## ¿Cómo actualizar el código después?

Cada vez que hagas cambios y los subas a GitHub, Streamlit Cloud
se actualiza automáticamente en ~30 segundos.

```bash
git add .
git commit -m "descripción del cambio"
git push
```

---

## Estructura de archivos que debe estar en GitHub

```
football-predictor/          ← raíz del repositorio
├── app.py
├── config.py
├── requirements.txt
├── .gitignore
├── .streamlit/
│   └── config.toml          ← ✅ sí subir
│   └── secrets.toml         ← ❌ NO subir (configurar en Streamlit Cloud)
├── data/
│   ├── __init__.py
│   ├── loader.py
│   ├── api_fetcher.py
│   ├── teams.json
│   └── players.json
├── predictor/
│   ├── __init__.py
│   ├── poisson_model.py
│   ├── player_model.py
│   └── tournament.py
└── pages/
    ├── 1_Partido.py
    ├── 2_Grupo.py
    ├── 3_Torneo.py
    ├── 4_Jugadores.py
    ├── 5_Gestionar_Equipos.py
    └── 6_Actualizar_Datos.py
```
