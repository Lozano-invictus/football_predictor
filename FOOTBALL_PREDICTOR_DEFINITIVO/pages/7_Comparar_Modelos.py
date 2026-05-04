import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from data.loader import DataLoader
from predictor.poisson_model import PoissonModel
from predictor.dixon_coles import DixonColesModel

st.set_page_config(page_title="Comparar Modelos", page_icon="⚖️", layout="wide")

st.title("⚖️ Comparativa de Modelos Predictivos")
st.markdown("""
Esta página permite comparar la distribución de Poisson estándar frente al modelo 
avanzado de **Dixon-Coles**, que ajusta la correlación en marcadores bajos.
""")

loader = DataLoader()
teams = loader.load_teams()
team_names = sorted([t["name"] for t in teams])

col1, col2 = st.columns(2)
with col1:
    home_name = st.selectbox("Local", team_names, index=team_names.index("Real Madrid") if "Real Madrid" in team_names else 0)
with col2:
    away_name = st.selectbox("Visitante", team_names, index=team_names.index("Manchester City") if "Manchester City" in team_names else 1)

home = loader.get_team(home_name)
away = loader.get_team(away_name)

if home and away:
    model_p = PoissonModel()
    model_dc = DixonColesModel()

    res_p = model_p.match_probabilities(home, away)
    res_dc = model_dc.match_probabilities(home, away)

    # Métricas comparativas
    st.divider()
    m1, m2, m3 = st.columns(3)
    
    with m1:
        diff_draw = (res_dc["draw"] - res_p["draw"]) * 100
        st.metric("Prob. Empate (DC)", f"{res_dc['draw']:.1%}", f"{diff_draw:+.2f}% vs Poisson")
    
    with m2:
        diff_home = (res_dc["home_win"] - res_p["home_win"]) * 100
        st.metric("Victoria Local (DC)", f"{res_dc['home_win']:.1%}", f"{diff_home:+.2f}% vs Poisson")
    
    with m3:
        diff_away = (res_dc["away_win"] - res_p["away_win"]) * 100
        st.metric("Victoria Visitante (DC)", f"{res_dc['away_win']:.1%}", f"{diff_away:+.2f}% vs Poisson")

    # Gráfico de barras comparativo
    labels = ["Victoria Local", "Empate", "Victoria Visitante"]
    vals_p = [res_p["home_win"], res_p["draw"], res_p["away_win"]]
    vals_dc = [res_dc["home_win"], res_dc["draw"], res_dc["away_win"]]

    fig = go.Figure(data=[
        go.Bar(name='Poisson', x=labels, y=vals_p, marker_color='#185FA5'),
        go.Bar(name='Dixon-Coles', x=labels, y=vals_dc, marker_color='#993C1D')
    ])
    fig.update_layout(barmode='group', title=f"Probabilidades: {home_name} vs {away_name}", yaxis_tickformat='.1%')
    st.plotly_chart(fig, use_container_width=True)

    # Comparativa de matrices (heatmap)
    st.subheader("Diferencia en Matriz de Marcadores (DC - Poisson)")
    diff_matrix = res_dc["score_matrix"] - res_p["score_matrix"]
    
    fig_hm = go.Figure(data=go.Heatmap(
        z=diff_matrix[:6, :6],
        x=[str(i) for i in range(6)],
        y=[str(i) for i in range(6)],
        colorscale='RdBu',
        zmid=0,
        text=np.around(diff_matrix[:6, :6] * 100, 2),
        texttemplate="%{text}%",
    ))
    fig_hm.update_layout(
        title="Azul: DC predice más probable | Rojo: Poisson predice más probable",
        xaxis_title=f"Goles {away_name}",
        yaxis_title=f"Goles {home_name}"
    )
    st.plotly_chart(fig_hm, use_container_width=True)
