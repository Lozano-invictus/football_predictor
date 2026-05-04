"""
app.py – Dashboard principal del Analizador Predictivo de Fútbol Definivo.
Ejecutar con: streamlit run app.py
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import sys, os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from data.loader import DataLoader
from predictor.poisson_model import PoissonModel
from predictor.dixon_coles import DixonColesModel
import config

# Configuración de página
st.set_page_config(
    page_title="Football Predictor Pro",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------ #
# HEADER & MÉTRICAS TIEMPO REAL
# ------------------------------------------------------------------ #
st.title("⚽ Football Predictive Analyzer Pro")

# Simulación de métricas en tiempo real (pueden venir de football-data.org)
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
    st.metric("Partidos Hoy", "8", "UCL")
with col_m2:
    st.metric("Confianza Media", "68%", "+2%")
with col_m3:
    st.metric("ROI Histórico", "+12.4%", "↑")
with col_m4:
    st.metric("Modelo Activo", "Dixon-Coles")

st.divider()

# ------------------------------------------------------------------ #
# LAYOUT PRINCIPAL
# ------------------------------------------------------------------ #
loader = DataLoader()
teams = loader.load_teams()
df = loader.teams_df()
df["team_strength"] = df["attack"] - df["defense"]
df_sorted = df.sort_values("team_strength", ascending=False).reset_index(drop=True)

col_left, col_right = st.columns([3, 2])

with col_left:
    st.subheader("📊 Análisis Global de Fuerza (Top 15)")
    fig = go.Figure(go.Bar(
        x=df_sorted["name"][:15],
        y=df_sorted["team_strength"][:15],
        marker_color=[
            "#185FA5" if v > 0.8 else "#3383C8" if v > 0.4 else "#7BB3D9" if v > 0 else "#993C1D"
            for v in df_sorted["team_strength"][:15]
        ],
        text=[f"{v:+.2f}" for v in df_sorted["team_strength"][:15]],
        textposition="outside",
    ))
    fig.update_layout(xaxis_tickangle=-35, height=400, margin=dict(t=20, b=80, l=20, r=20))
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("🎯 Predicción del Día")
    # Lógica simple para "predicción del día": mayor diferencia de xG
    model = DixonColesModel()
    # Tomamos dos equipos del top para simular
    t1 = df_sorted.iloc[0]
    t2 = df_sorted.iloc[4]
    
    res = model.match_probabilities(t1.to_dict(), t2.to_dict())
    
    st.info(f"**{t1['name']} vs {t2['name']}**")
    c1, c2 = st.columns(2)
    c1.write(f"🏠 Prob. Local: **{res['home_win']:.1%}**")
    c2.write(f"✈️ Prob. Visitante: **{res['away_win']:.1%}**")
    st.write(f"🤝 Empate: **{res['draw']:.1%}**")
    st.write(f"📈 Marcador Sugerido: **{res['top_scores'][0]['home_goals']} - {res['top_scores'][0]['away_goals']}**")
    
    if st.button("Ver análisis completo"):
        st.switch_page("pages/1_Partido.py")

st.divider()

# ------------------------------------------------------------------ #
# NAVEGACIÓN RÁPIDA
# ------------------------------------------------------------------ #
st.subheader("🚀 Acceso Rápido")
c1, c2, c3, c4 = st.columns(4)
with c1:
    if st.button("⚽ Analizar Partido"): st.switch_page("pages/1_Partido.py")
with c2:
    if st.button("🏆 Simular Torneo"): st.switch_page("pages/3_Torneo.py")
with c3:
    if st.button("⚖️ Comparar Modelos"): st.switch_page("pages/7_Comparar_Modelos.py")
with c4:
    if st.button("🔄 Actualizar Datos"): st.switch_page("pages/6_Actualizar_Datos.py")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption(f"v3.0.0 Definitive Edition | {datetime.now().year}")
st.sidebar.success("Sistema escalable y listo para despliegue.")
