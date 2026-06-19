
import streamlit as st
import logging

# Añadir raíz al path para importar módulos locales

from data.api_fetcher import DataUpdater
from data.elo_engine import EloEngine
from data.loader import DataLoader
from data.database import init_db
from utils import get_secret

# Configurar logging
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Panel de Control", page_icon="🔧", layout="wide")

st.title("🔧 Panel de Administración")
st.markdown("Gestiona la actualización de datos y el sistema de Elo")

# Tab de navegación
tab1, tab2, tab3 = st.tabs(["📥 Actualizar Datos", "🏆 Sistema Elo", "📊 Dashboard"])


# ============================================================ #
# TAB 1: ACTUALIZAR DATOS
# ============================================================ #
with tab1:
    st.header("📥 Actualizar Base de Datos")
    st.markdown("Actualiza la base de datos con información real desde football-data.org")

    # Cargar API key (fail-fast; no pedirla en UI)
    # FASE D: secrets hardening (no fallar si no existe secrets.toml)
    API_KEY = get_secret("FOOTBALL_DATA_API_KEY") or get_secret("FOOTBALL_DATA_KEY")

    if not API_KEY:
        st.warning(
            "⚠️ No se encontró la clave de la API. Añádela en variables de entorno "
            "o en st.secrets (FOOTBALL_DATA_API_KEY)."
        )
        st.stop()

    st.success("✅ API Key detectada correctamente!")

    # Opciones de actualización
    st.subheader("Opciones de Actualización")
    season = st.selectbox("Temporada a actualizar", [2023, 2022, 2024, 2025], index=0,
                         help="Temporada 2023 tiene datos completos disponibles")
    competition = st.selectbox("Competición", ["Champions League", "Todas las competiciones"], index=0)

    # Determinar qué competiciones actualizar
    competitions = None
    if competition == "Champions League":
        competitions = {"Champions League": "CL"}

    # Antiejecución duplicada (evita múltiples runs por refresco)
    if "_updating" not in st.session_state:
        st.session_state["_updating"] = False

    # Botón de actualización
    can_run = not st.session_state["_updating"]
    if st.button("🚀 Actualizar Base de Datos", type="primary", disabled=not can_run):
        st.session_state["_updating"] = True
        st.subheader("Resultado de la Actualización")
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text("Iniciando actualización...")
            progress_bar.progress(10)

            updater = DataUpdater(API_KEY)
            status_text.text("Actualizando equipos...")
            progress_bar.progress(30)

            teams_result = updater.update_teams_in_db(competitions, season)
            progress_bar.progress(60)
            status_text.text("Actualizando goleadores...")

            scorers_result = updater.update_scorers_in_db("CL", season)
            progress_bar.progress(100)
            status_text.text("✅ Actualización completada!")

            # Mostrar resultados
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Equipos")
                st.metric("Actualizados", teams_result["updated"])
                if teams_result["errors"]:
                    st.error(f"Errores: {len(teams_result['errors'])}")
                    for err in teams_result["errors"]:
                        st.write(f"- {err['league']}: {err['error']}")

            with col2:
                st.subheader("Goleadores")
                st.metric("Actualizados", scorers_result["updated"])

            st.success("🎉 Base de datos actualizada exitosamente!")

            # Actualizar datos en la sesión de Streamlit
            st.session_state.data_loader = DataLoader()
            st.info("Los datos se han actualizado — navega por las páginas para ver los cambios!")

        except Exception as e:
            st.error(f"❌ Error durante la actualización: {e}")
            logger.exception("Error en la actualización")
            st.stop()
        finally:
            st.session_state["_updating"] = False


# ============================================================ #
# TAB 2: SISTEMA ELO
# ============================================================ #
with tab2:
    st.header("🏆 Sistema de Ratings Elo")
    elo_engine = EloEngine()

    # Ver Top 10 equipos
    st.subheader("Top 10 Equipos por Elo")
    top_teams = elo_engine.get_top_teams(10)

    for i, team in enumerate(top_teams, 1):
        col1, col2, col3 = st.columns([1, 3, 2])
        with col1:
            st.write(f"**{i}**")
        with col2:
            st.write(f"{team['name']}")
        with col3:
            st.metric("Elo Rating", f"{team['elo']:.2f}")

    st.divider()

    # Acciones para Elo
    st.subheader("Acciones de Elo")
    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("🔄 Reconstruir Historial de Elo", type="secondary"):
            with st.spinner("Reconstruyendo historial de Elo..."):
                result = elo_engine.rebuild_all_elo_history(start_season="2022-23")
                if result["status"] == "success":
                    st.success(f"✅ Historial reconstruido!")
                    st.metric("Partidos procesados", result["processed_matches"])
                    st.metric("Errores", result["errors"])
                else:
                    st.error(f"❌ Error: {result['message']}")

    with col2:
        st.write("🔹 El motor de Elo calcula ratings automáticamente con cada partido nuevo")


# ============================================================ #
# TAB 3: DASHBOARD RÁPIDO
# ============================================================ #
with tab3:
    st.header("📊 Estado del Sistema")

    # Cargar datos para mostrar
    loader = DataLoader()
    teams = loader.load_teams()
    players = loader.load_players()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Equipos en BD", len(teams))
    with col2:
        st.metric("Jugadores en BD", len(players))
    with col3:
        st.metric("Estado de BD", "✅ Activa")


# Información adicional
st.markdown("""
---
### ℹ️ Información
- **Fuente**: football-data.org
- **Límite API Gratuita**: 10 requests/minuto
- **Datos actualizados**: Equipos, goleadores, estadísticas básicas
- **Sistema Elo**: Actualiza ratings automáticamente con resultados de partidos
""")
