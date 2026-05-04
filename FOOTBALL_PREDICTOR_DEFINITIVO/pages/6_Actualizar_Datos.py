"""
pages/6_Actualizar_Datos.py
Panel de actualización de datos desde football-data.org (API gratuita).
"""
import streamlit as st
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.loader import DataLoader

st.set_page_config(page_title="Actualizar Datos", page_icon="🔄", layout="wide")
st.title("🔄 Actualizar Datos desde API Real")

# ------------------------------------------------------------------ #
# INSTRUCCIONES
# ------------------------------------------------------------------ #
with st.expander("📋 ¿Cómo obtener tu API key gratuita? (clic para ver)", expanded=False):
    st.markdown("""
    ### Pasos para obtener tu API key GRATIS

    1. Ve a **[football-data.org/client/register](https://www.football-data.org/client/register)**
    2. Regístrate con tu email (es gratis, no pide tarjeta)
    3. Recibirás tu **API key** por email en segundos
    4. Pégala en el campo de abajo

    ### ¿Qué datos incluye el plan gratuito?
    | Datos | ✅ Gratis |
    |-------|----------|
    | Equipos UCL, Premier, La Liga, Serie A, Bundesliga, Ligue 1 | ✅ |
    | Resultados de partidos | ✅ |
    | Goleadores | ✅ |
    | Standings / clasificación | ✅ |
    | Datos en tiempo real (live) | ❌ (plan de pago) |

    ### Límite de llamadas
    - **10 llamadas por minuto** en el plan gratuito
    - El sistema gestiona automáticamente los tiempos de espera
    """)

# ------------------------------------------------------------------ #
# API KEY
# ------------------------------------------------------------------ #
st.divider()
st.subheader("🔑 Configuración de API")

# Intentar leer key del entorno (para Streamlit Cloud)
env_key = os.getenv("FOOTBALL_DATA_KEY", "")

api_key = st.text_input(
    "API Key de football-data.org",
    value=env_key,
    type="password",
    placeholder="Pega aquí tu API key gratuita...",
    help="Regístrate gratis en football-data.org para obtenerla"
)

if api_key:
    st.success("✅ API key cargada")
else:
    st.warning("⚠️ Ingresa tu API key para poder actualizar los datos")

# ------------------------------------------------------------------ #
# SELECCIÓN DE COMPETICIONES
# ------------------------------------------------------------------ #
st.divider()
st.subheader("⚙️ Qué datos actualizar")

COMPETITION_CODES = {
    "🏆 Champions League": "CL",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League":   "PL",
    "🇪🇸 La Liga":          "PD",
    "🇮🇹 Serie A":           "SA",
    "🇩🇪 Bundesliga":        "BL1",
    "🇫🇷 Ligue 1":           "FL1",
}

col1, col2 = st.columns(2)
with col1:
    selected_comps = st.multiselect(
        "Competiciones a actualizar",
        list(COMPETITION_CODES.keys()),
        default=["🏆 Champions League"],
        help="Cada competición consume ~3-5 llamadas a la API"
    )
    season = st.selectbox(
        "Temporada",
        [2024, 2023, 2022, 2021],
        index=0,
        help="2024 = temporada 2024-25"
    )

with col2:
    update_teams   = st.checkbox("Actualizar equipos y estadísticas", value=True)
    update_scorers = st.checkbox("Actualizar goleadores", value=True)
    st.caption(f"Competiciones seleccionadas: **{len(selected_comps)}**")
    calls_est = len(selected_comps) * 3
    st.caption(f"Llamadas estimadas a la API: ~**{calls_est}**")
    time_est = max(1, calls_est // 10)
    st.caption(f"Tiempo estimado: ~**{time_est}-{time_est*2} minutos**")

# ------------------------------------------------------------------ #
# BOTÓN DE ACTUALIZACIÓN
# ------------------------------------------------------------------ #
st.divider()

if st.button("🚀 Iniciar actualización", type="primary",
             disabled=not api_key or not selected_comps):
    try:
        from data.api_fetcher import DataUpdater, COMPETITION_CODES as ALL_CODES

        # Mapear selección a códigos
        comps_to_update = {
            name.split(" ", 1)[1]: COMPETITION_CODES[name]
            for name in selected_comps
        }

        updater = DataUpdater(api_key)
        results = {}

        progress = st.progress(0, text="Conectando con la API...")
        status_box = st.empty()

        total_steps = (len(comps_to_update) if update_teams else 0) + \
                      (1 if update_scorers else 0)
        step = 0

        if update_teams:
            for league, code in comps_to_update.items():
                status_box.info(f"📡 Obteniendo datos de **{league}**…")
                r = updater.update_teams({league: code}, season)
                results[f"equipos_{league}"] = r
                step += 1
                progress.progress(step / total_steps,
                                   text=f"✅ {league} completado")

        if update_scorers and "Champions League" in comps_to_update.values() or \
           "CL" in comps_to_update.values():
            status_box.info("📡 Actualizando goleadores UCL…")
            r2 = updater.update_scorers("CL", season)
            results["goleadores_UCL"] = r2
            step += 1
            progress.progress(1.0, text="✅ Goleadores actualizados")
        elif update_scorers:
            first_code = list(comps_to_update.values())[0]
            status_box.info(f"📡 Actualizando goleadores…")
            r2 = updater.update_scorers(first_code, season)
            results["goleadores"] = r2
            progress.progress(1.0)

        status_box.empty()
        st.success("✅ ¡Actualización completada!")

        # Mostrar resumen
        total_equipos = sum(
            v.get("updated", 0) for k, v in results.items()
            if k.startswith("equipos")
        )
        total_jugadores = results.get("goleadores_UCL", {}).get("updated", 0)

        m1, m2, m3 = st.columns(3)
        m1.metric("Equipos actualizados", total_equipos)
        m2.metric("Goleadores actualizados", total_jugadores)
        m3.metric("Timestamp", results.get(
            "goleadores_UCL", list(results.values())[0]
        ).get("timestamp", "—")[:10])

        with st.expander("Ver resultado completo"):
            st.json(results)

    except ImportError:
        st.error("Instala las dependencias: `pip install requests`")
    except Exception as e:
        st.error(f"❌ Error durante la actualización: {e}")
        st.exception(e)

# ------------------------------------------------------------------ #
# ESTADO ACTUAL DE LOS DATOS
# ------------------------------------------------------------------ #
st.divider()
st.subheader("📊 Estado actual de la base de datos")

loader = DataLoader()
teams  = loader.load_teams()
players = loader.load_players("strikers")
gks     = loader.load_players("goalkeepers")
defs    = loader.load_players("defenders")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Equipos", len(teams))
c2.metric("Delanteros", len(players))
c3.metric("Porteros", len(gks))
c4.metric("Defensas", len(defs))

# Mostrar fecha de última actualización si existe
try:
    with open("data/teams.json") as f:
        meta = json.load(f).get("metadata", {})
    if "last_updated" in meta:
        st.caption(f"Última actualización: **{meta['last_updated']}**")
except Exception:
    pass

# ------------------------------------------------------------------ #
# ACTUALIZACIÓN MANUAL RÁPIDA (sin API)
# ------------------------------------------------------------------ #
st.divider()
st.subheader("✏️ Actualización manual rápida de un equipo")
st.caption("Si no tienes API key, puedes actualizar estadísticas manualmente aquí.")

with st.form("quick_update"):
    teams_names = [t["name"] for t in teams]
    team_sel = st.selectbox("Equipo", teams_names)
    c1, c2 = st.columns(2)
    new_att = c1.number_input("Media goles anotados/partido",
                               0.5, 5.0, value=float(
        next(t["attack"] for t in teams if t["name"] == team_sel)
    ), step=0.05)
    new_def = c2.number_input("Media goles encajados/partido",
                               0.2, 4.0, value=float(
        next(t["defense"] for t in teams if t["name"] == team_sel)
    ), step=0.05)
    if st.form_submit_button("💾 Guardar cambio"):
        loader.add_or_update_team({
            "name":    team_sel,
            "attack":  new_att,
            "defense": new_def,
        })
        st.success(f"✅ {team_sel} actualizado: att={new_att}, def={new_def}")
        st.rerun()
