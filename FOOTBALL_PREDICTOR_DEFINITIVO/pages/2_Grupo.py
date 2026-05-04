"""
pages/2_Grupo.py
Simulador de fase de grupos.
"""
import streamlit as st
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.loader import DataLoader
from predictor.poisson_model import PoissonModel

st.set_page_config(page_title="Fase de Grupos", page_icon="🏆", layout="wide")
st.title("🏆 Simulador de Fase de Grupos")
st.caption("Selecciona 4 equipos y simula un grupo completo (round-robin doble)")

loader = DataLoader()
model  = PoissonModel()
teams  = loader.load_teams()
names  = [t["name"] for t in teams]
t_map  = {t["name"]: t for t in teams}

# ------------------------------------------------------------------ #
# SELECCIÓN DE 4 EQUIPOS
# ------------------------------------------------------------------ #
st.subheader("Configura el grupo")
defaults = [names[0], names[6], names[10], names[14]]

cols = st.columns(4)
selected = []
for i, col in enumerate(cols):
    opts = [n for n in names if n not in selected]
    default_idx = opts.index(defaults[i]) if defaults[i] in opts else 0
    pick = col.selectbox(f"Equipo {i+1}", opts, index=default_idx, key=f"grp_{i}")
    selected.append(pick)

# ------------------------------------------------------------------ #
# SIMULACIÓN
# ------------------------------------------------------------------ #
group_teams = [t_map[n] for n in selected]
df = model.simulate_group(group_teams)

# ------------------------------------------------------------------ #
# TABLA DE CLASIFICACIÓN
# ------------------------------------------------------------------ #
st.divider()
st.subheader("Tabla de clasificación simulada")

def style_row(row):
    pos = row.name
    if pos <= 2:
        return ["background-color: rgba(24,95,165,0.15)"] * len(row)
    return [""] * len(row)

st.dataframe(
    df.style.apply(style_row, axis=1).format({"GF": "{:.1f}", "GC": "{:.1f}", "DG": "{:.1f}"}),
    use_container_width=True,
    height=210,
)
st.caption("🔵 Los dos primeros clasifican a la siguiente ronda.")

# ------------------------------------------------------------------ #
# GRÁFICO DE PUNTOS
# ------------------------------------------------------------------ #
st.subheader("Puntos y diferencia de goles")
fig = go.Figure()
colors = ["#185FA5", "#3383C8", "#993C1D", "#C45A3A"]
for i, (_, row) in enumerate(df.iterrows()):
    fig.add_trace(go.Bar(
        name=row["Equipo"],
        x=[row["Equipo"]],
        y=[row["Pts"]],
        marker_color=colors[i % len(colors)],
        text=f"{row['Pts']} pts",
        textposition="outside",
    ))
fig.update_layout(
    showlegend=False,
    yaxis_title="Puntos",
    height=320,
    margin=dict(t=20, b=20, l=20, r=20),
)
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------ #
# MATRIZ DE ENFRENTAMIENTOS
# ------------------------------------------------------------------ #
st.subheader("Probabilidades de victoria por enfrentamiento")

n = len(group_teams)
matrix_labels = [t["name"][:12] for t in group_teams]
z = [[None]*n for _ in range(n)]
text_matrix = [["—"]*n for _ in range(n)]

for i, h in enumerate(group_teams):
    for j, a in enumerate(group_teams):
        if i != j:
            r = model.match_probabilities(h, a)
            z[i][j] = round(r["home_win"]*100, 1)
            text_matrix[i][j] = f"{z[i][j]:.0f}%"

fig_mx = go.Figure(go.Heatmap(
    z=z,
    x=matrix_labels,
    y=matrix_labels,
    text=text_matrix,
    texttemplate="%{text}",
    colorscale="Blues",
    showscale=True,
    colorbar=dict(title="P(victoria fila) %"),
    zmin=0, zmax=100,
))
fig_mx.update_layout(
    xaxis_title="Visitante",
    yaxis_title="Local",
    height=360,
    margin=dict(t=20, b=20, l=80, r=20),
)
st.plotly_chart(fig_mx, use_container_width=True)
