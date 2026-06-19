"""
pages/3_Torneo.py
Simulador Monte Carlo de torneo eliminatorio completo.
"""
import streamlit as st
import plotly.graph_objects as go

from data.loader import DataLoader
from predictor.poisson_model import PoissonModel
from predictor.dixon_coles import DixonColesModel
from predictor.tournament import TournamentSimulator

st.set_page_config(page_title="Simulador de Torneo", page_icon="🎯", layout="wide")
st.title("🎯 Simulador Monte Carlo de Torneo")

# Selección de Modelo para el torneo
model_type = st.sidebar.radio("Modelo para Simulación", ["Poisson", "Dixon-Coles"])
st.caption(f"Modelo activo: {model_type} · Simulación estocástica mediante muestreo de Poisson en cada partido")

loader = DataLoader()
if model_type == "Poisson":
    model = PoissonModel()
else:
    model = DixonColesModel()
teams  = loader.load_teams()
names  = [t["name"] for t in teams]
t_map  = {t["name"]: t for t in teams}

if len(names) < 4:
    st.warning("Necesitas al menos 4 equipos cargados para simular un torneo. Ve a 'Actualizar Datos'.")
    st.stop()

# ------------------------------------------------------------------ #
# CONFIGURACIÓN
# ------------------------------------------------------------------ #
st.sidebar.header("⚙️ Configuración")
n_sims = st.sidebar.slider("Número de simulaciones", 500, 10000, 2000, step=500)
team_size_options = [n for n in [4, 8, 16] if n <= len(names)]
n_teams = st.sidebar.selectbox("Equipos en el torneo", team_size_options, index=min(1, len(team_size_options) - 1))

st.subheader(f"Selecciona {n_teams} equipos")

default_positions = [0, 6, 10, 14, 2, 7, 11, 15]
defaults_all = [names[i] if i < len(names) else names[0] for i in default_positions]
cols = st.columns(4)
selected = []
for i in range(n_teams):
    col = cols[i % 4]
    opts = [n for n in names if n not in selected]
    default = defaults_all[i] if i < len(defaults_all) else opts[0]
    default_idx = opts.index(default) if default in opts else 0
    pick = col.selectbox(f"Equipo {i+1}", opts, index=default_idx, key=f"t_{i}")
    selected.append(pick)

# ------------------------------------------------------------------ #
# SIMULACIÓN
# ------------------------------------------------------------------ #
st.divider()
if st.button("▶️ Simular torneo", type="primary"):
    sim_teams = [t_map[n] for n in selected]
    simulator = TournamentSimulator(model=model, n_simulations=n_sims)

    with st.spinner(f"Simulando {n_sims:,} torneos..."):
        results = simulator.simulate_champion(sim_teams)

    sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)

    # --- Métricas top 3 ---
    top3 = sorted_results[:3]
    c1, c2, c3 = st.columns(3)
    medals = ["🥇", "🥈", "🥉"]
    for (name, prob), col, medal in zip(top3, [c1, c2, c3], medals):
        col.metric(f"{medal} {name}", f"{prob*100:.1f}%", help="P(campeón)")

    # --- Gráfico de barras horizontal ---
    names_sorted = [r[0] for r in sorted_results]
    probs_sorted  = [r[1]*100 for r in sorted_results]
    colors = ["#185FA5" if i == 0 else "#3383C8" if i == 1 else "#7BB3D9" if i < 4 else "#AECDE8"
              for i in range(len(names_sorted))]

    fig = go.Figure(go.Bar(
        y=names_sorted[::-1],
        x=probs_sorted[::-1],
        orientation="h",
        marker_color=colors[::-1],
        text=[f"{p:.1f}%" for p in probs_sorted[::-1]],
        textposition="outside",
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        title=f"Probabilidad de ganar el torneo ({n_sims:,} simulaciones)",
        xaxis_title="Probabilidad (%)",
        xaxis_range=[0, max(probs_sorted)*1.15],
        height=max(300, n_teams * 42),
        margin=dict(t=40, b=20, l=160, r=60),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- Tabla resumen ---
    st.subheader("Tabla de probabilidades completa")
    import pandas as pd
    df = pd.DataFrame(sorted_results, columns=["Equipo", "P(campeón)"])
    df["P(campeón)"] = (df["P(campeón)"] * 100).round(1).astype(str) + " %"
    df.index = range(1, len(df)+1)
    df.index.name = "Pos"
    st.dataframe(df, use_container_width=True)

else:
    st.info("Configura los equipos y pulsa **Simular torneo** para comenzar.")
