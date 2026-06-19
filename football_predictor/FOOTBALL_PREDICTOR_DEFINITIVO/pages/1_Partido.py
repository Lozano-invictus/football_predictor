"""
pages/1_Partido.py
Análisis predictivo de un partido individual.
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

from data.loader import DataLoader
from predictor.poisson_model import PoissonModel
from predictor.dixon_coles import DixonColesModel
from data.database import get_session, Prediction, Team

st.set_page_config(page_title="Análisis de Partido", page_icon="⚽", layout="wide")
st.title("⚽ Análisis Predictivo de Partido")

# ------------------------------------------------------------------ #
# SELECCIÓN DE MODELO
# ------------------------------------------------------------------ #
model_type = st.sidebar.radio("Modelo Predictivo", ["Poisson", "Dixon-Coles (Avanzado)"])
st.caption(f"Modelo activo: {model_type} · ventaja local · team strength")

loader = DataLoader()
if model_type == "Poisson":
    model = PoissonModel()
else:
    model = DixonColesModel()

teams  = loader.load_teams()
names  = [t["name"] for t in teams]
t_map  = {t["name"]: t for t in teams}

if len(names) < 2:
    st.warning("Necesitas al menos 2 equipos cargados para analizar un partido. Ve a 'Actualizar Datos'.")
    st.stop()

# ------------------------------------------------------------------ #
# SELECCIÓN DE EQUIPOS
# ------------------------------------------------------------------ #
col1, col2 = st.columns(2)
with col1:
    home_name = st.selectbox("🏠 Equipo local", names, index=0)
with col2:
    away_opts = [n for n in names if n != home_name]
    away_name = st.selectbox("✈️ Equipo visitante", away_opts,
                              index=min(6, len(away_opts)-1))

home = t_map[home_name]
away = t_map[away_name]

# ------------------------------------------------------------------ #
# CÁLCULO
# ------------------------------------------------------------------ #
try:
    result = model.match_probabilities(home, away)
except Exception as e:
    st.error(f"Error calculando probabilidades: {e}")
    st.stop()

# ------------------------------------------------------------------ #
# KPIs
# ------------------------------------------------------------------ #
st.divider()
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("xG Local",      f"{result['expected_home']:.2f}")
k2.metric("xG Visitante",  f"{result['expected_away']:.2f}")
k3.metric("Victoria local",   f"{result['home_win']*100:.1f}%")
k4.metric("Empate",           f"{result['draw']*100:.1f}%")
k5.metric("Victoria visitante",f"{result['away_win']*100:.1f}%")

# ------------------------------------------------------------------ #
# GRÁFICOS LADO A LADO
# ------------------------------------------------------------------ #
st.divider()
g1, g2 = st.columns([1, 1])

# --- Donut probabilidades ---
with g1:
    st.subheader("Probabilidades de resultado")
    fig_donut = go.Figure(go.Pie(
        labels=[f"Victoria {home_name}", "Empate", f"Victoria {away_name}"],
        values=[result["home_win"], result["draw"], result["away_win"]],
        hole=0.55,
        marker_colors=["#185FA5", "#888780", "#993C1D"],
        textinfo="label+percent",
        hovertemplate="%{label}: %{percent}<extra></extra>",
    ))
    fig_donut.update_layout(
        margin=dict(t=20, b=20, l=20, r=20),
        showlegend=False,
        height=320,
    )
    st.plotly_chart(fig_donut, use_container_width=True)

# --- Marcadores más probables ---
with g2:
    st.subheader("Marcadores más probables")
    top = result["top_scores"][:8]
    labels = [f"{s['home_goals']}–{s['away_goals']}" for s in top]
    probs  = [round(s["probability"]*100, 2) for s in top]
    colors = []
    for s in top:
        if s["home_goals"] > s["away_goals"]:
            colors.append("#185FA5")
        elif s["home_goals"] == s["away_goals"]:
            colors.append("#888780")
        else:
            colors.append("#993C1D")

    fig_bar = go.Figure(go.Bar(
        x=labels, y=probs,
        marker_color=colors,
        text=[f"{p}%" for p in probs],
        textposition="outside",
        hovertemplate="%{x}: %{y}%<extra></extra>",
    ))
    fig_bar.update_layout(
        yaxis_title="Probabilidad (%)",
        margin=dict(t=20, b=30, l=20, r=20),
        height=320,
        showlegend=False,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# ------------------------------------------------------------------ #
# HEATMAP MATRIZ DE PROBABILIDADES
# ------------------------------------------------------------------ #
st.subheader("Matriz de probabilidades de marcador")
matrix = result["score_matrix"][:7, :7] * 100   # mostrar 0-6 goles

fig_heat = px.imshow(
    np.round(matrix, 2),
    labels=dict(x=f"Goles {away_name}", y=f"Goles {home_name}", color="P (%)"),
    x=[str(i) for i in range(7)],
    y=[str(i) for i in range(7)],
    color_continuous_scale="Blues",
    text_auto=".1f",
    aspect="auto",
)
fig_heat.update_layout(height=380, margin=dict(t=20, b=20, l=60, r=20))
st.plotly_chart(fig_heat, use_container_width=True)

# ------------------------------------------------------------------ #
# ELIMINATORIA (ida + vuelta)
# ------------------------------------------------------------------ #
st.divider()
st.subheader("🔁 Simulación eliminatoria (ida y vuelta)")
try:
    tie = model.two_leg_tie(home, away)
    c1, c2 = st.columns(2)
    c1.metric(f"P(clasifica {home_name})", f"{tie['team1_qualify']*100:.1f}%")
    c2.metric(f"P(clasifica {away_name})", f"{tie['team2_qualify']*100:.1f}%")
except AttributeError:
    st.info("Nota: La simulación de eliminatoria (ida/vuelta) solo está disponible en el modelo Poisson estándar.")
except Exception as e:
    st.error(f"Error en simulación de eliminatoria: {e}")

# ------------------------------------------------------------------ #
# GUARDAR EN BASE DE DATOS
# ------------------------------------------------------------------ #
if st.button("💾 Guardar Predicción en Historial"):
    session = get_session()
    try:
        # Obtener IDs de equipos
        h_team = session.query(Team).filter_by(name=home_name).first()
        a_team = session.query(Team).filter_by(name=away_name).first()

        if not h_team or not a_team:
            st.error("No se pudo guardar: faltan IDs de equipos en la base de datos.")
            st.stop()
        
        pred = Prediction(
            home_team_id=h_team.id,
            away_team_id=a_team.id,
            model_used=model_type,
            prob_home=result["home_win"],
            prob_draw=result["draw"],
            prob_away=result["away_win"],
            expected_home=result["expected_home"],
            expected_away=result["expected_away"]
        )
        session.add(pred)
        session.commit()
        st.success("✅ Predicción guardada con éxito.")
    except Exception as e:
        st.error(f"Error guardando predicción: {e}")
    finally:
        session.close()
