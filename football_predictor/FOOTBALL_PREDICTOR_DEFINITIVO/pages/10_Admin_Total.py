"""
pages/10_Admin_Total.py
Panel Administrativo para la Gestión Total de Datos UCL (2022-2026).
Permite actualizaciones masivas, ETL incremental y monitoreo de base de datos.
"""
import streamlit as st
import pandas as pd
from data.database import get_session, Team, Player, PlayerSeasonStats, Transfer, TeamSeasonStats, Match
from data.etl_master import ETLMasterPro
from data.data_quality import run_quality_audit
import config
import os

# FASE E: dependencia opcional (no romper carga de la página si falta)
try:
    from thefuzz import process, fuzz
except ImportError:
    class _NoopProcess:
        @staticmethod
        def extract(*args, **kwargs):
            return []

    class _NoopFuzz:
        token_sort_ratio = None

    process = _NoopProcess()
    fuzz = _NoopFuzz()

st.set_page_config(page_title="Admin Total UCL", page_icon="⚙️", layout="wide")

st.title("⚙️ Panel Administrativo de Datos (UCL TOTAL)")
st.markdown("""
Este panel permite gestionar la base de datos relacional que abarca desde la temporada 2022/23 
hasta la actual.
""")

session = get_session()

# --- KPIs del Sistema ---
c1, c2, c3, c4 = st.columns(4)
try:
    c1.metric("Equipos Totales", session.query(Team).count())
    c2.metric("Jugadores Registrados", session.query(Player).count())
    c3.metric("Registros Temporales", session.query(PlayerSeasonStats).count())
    c4.metric("Transferencias", session.query(Transfer).count())
except Exception as e:
    st.error(f"Error al conectar con la base de datos: {e}")

st.divider()

# --- Acciones de Actualización ---
col_actions, col_logs = st.columns([2, 1])

with col_actions:
    st.subheader("🚀 Acciones Masivas")
    
    if st.button("🔥 Re-importar Todo (CHAMPIONS_LEUE_PRO)"):
        with st.spinner("Ejecutando ETL Maestro..."):
            # Usar ruta relativa dinámica en lugar de hardcodeada
            base_path = os.path.join(
                os.path.dirname(os.path.dirname(config.PROJECT_ROOT)), 
                "CHAMPIONS_LEUE_PRO"
            )
            if not os.path.exists(base_path):
                st.error(f"❌ Ruta no encontrada: {base_path}")
                st.info("Asegúrate de que la carpeta CHAMPIONS_LEUE_PRO existe.")
            else:
                etl = ETLMasterPro(base_path)
                etl.run_full_ingestion()
                st.success("🎉 Datos históricos importados y normalizados.")
                st.rerun()

    if st.button("Auditar Calidad de Datos"):
        audit = run_quality_audit()
        status = audit["status"]
        if status == "OK":
            st.success("Auditoria OK: no se detectaron hallazgos criticos.")
        elif status == "WARN":
            st.warning("Auditoria con advertencias.")
        else:
            st.error("Auditoria con fallos de alta prioridad.")

        st.write("Conteos principales")
        st.json(audit["counts"])

        findings = audit["findings"]
        if findings:
            st.write("Hallazgos")
            for finding in findings:
                st.markdown(f"**{finding['severity']} | {finding['code']}**")
                st.write(finding["message"])
                if finding.get("sample"):
                    st.dataframe(pd.DataFrame(finding["sample"]), use_container_width=True)
        else:
            st.info("Sin hallazgos.")

    if st.button("🔍 Validar Integridad de Datos"):
        orphans = session.query(PlayerSeasonStats).filter(PlayerSeasonStats.team_id == None).count()
        st.write(f"Jugadores sin equipo: {orphans}")
        missing_stats = session.query(Team).filter(~Team.stats.any()).count()
        st.write(f"Equipos sin estadísticas: {missing_stats}")

st.divider()

# --- Gestión de Conflictos de Nombres ---
st.subheader("🤝 Resolución de Conflictos (Normalización)")
tab_conf_teams, tab_conf_players = st.tabs(["Equipos", "Jugadores"])

with tab_conf_teams:
    st.write("Equipos detectados con nombres similares que podrían ser el mismo:")
    # Lógica simple de detección de duplicados por fuzzy
    teams = session.query(Team).all()
    team_names = [t.name for t in teams]
    for name in team_names[:20]: # Limitado para demo
        matches = process.extract(name, [n for n in team_names if n != name], limit=1, scorer=fuzz.token_sort_ratio)
        if matches and matches[0][1] > 80:
            st.warning(f"Posible duplicado: **{name}** <-> **{matches[0][0]}** (Score: {matches[0][1]})")

# --- Explorador de Datos ---
st.subheader("🔍 Explorador de Base de Datos")
table_name = st.selectbox("Seleccionar Tabla", 
                          ["Equipos", "Estadísticas Equipo", "Jugadores", "Estadísticas Jugador", "Transferencias"])

if table_name == "Equipos":
    df = pd.read_sql(session.query(Team).statement, session.bind)
    st.dataframe(df, use_container_width=True)
elif table_name == "Estadísticas Equipo":
    df = pd.read_sql(session.query(TeamSeasonStats).statement, session.bind)
    st.dataframe(df, use_container_width=True)
elif table_name == "Jugadores":
    df = pd.read_sql(session.query(Player).statement, session.bind)
    st.dataframe(df, use_container_width=True)
elif table_name == "Estadísticas Jugador":
    df = pd.read_sql(session.query(PlayerSeasonStats).statement, session.bind)
    st.dataframe(df, use_container_width=True)
elif table_name == "Transferencias":
    df = pd.read_sql(session.query(Transfer).statement, session.bind)
    st.dataframe(df, use_container_width=True)

session.close()
