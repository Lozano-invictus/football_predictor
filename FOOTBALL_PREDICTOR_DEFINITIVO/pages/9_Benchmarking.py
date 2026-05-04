"""
pages/9_Benchmarking.py
Módulo de comparación con predicciones externas y mercado.
Calcula el error y la ventaja competitiva del modelo propio.
"""
import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.loader import DataLoader
from predictor.hybrid_model import HybridModel

st.set_page_config(page_title="Benchmarking Mercado", page_icon="⚖️", layout="wide")

st.title("⚖️ Comparación con el Mercado (Benchmarking)")
st.markdown("""
Ingresa las probabilidades de una fuente externa (ej: Casa de apuestas o PredictBet) 
para compararlas con las de nuestra IA.
""")

loader = DataLoader()
teams = loader.load_teams()
team_names = sorted([t["name"] for t in teams])

c1, c2 = st.columns(2)
home = c1.selectbox("Local", team_names, index=0)
away = c2.selectbox("Visitante", team_names, index=1)

st.divider()

col_ours, col_market = st.columns(2)

with col_ours:
    st.subheader("🤖 Nuestra IA (Dixon-Coles + Elo Híbrido)")
    model = HybridModel()
    
    # Asegurar que los equipos existen en el loader
    try:
        t_h = next(t for t in teams if t["name"] == home)
        t_a = next(t for t in teams if t["name"] == away)
        res = model.predict_hybrid(t_h, t_a, season="2025-2026")
        
        st.metric("Victoria Local", f"{res['home_win']:.1%}")
        st.metric("Empate", f"{res['draw']:.1%}")
        st.metric("Victoria Visitante", f"{res['away_win']:.1%}")
    except StopIteration:
        st.error("Error: Uno de los equipos seleccionados no se encuentra en la base de datos.")
        st.stop()

with col_market:
    st.subheader("🏢 Predicción Externa / Mercado")
    m_h = st.number_input("Prob. Victoria Local (%)", 0.0, 100.0, 45.0) / 100
    m_d = st.number_input("Prob. Empate (%)", 0.0, 100.0, 25.0) / 100
    m_a = st.number_input("Prob. Victoria Visitante (%)", 0.0, 100.0, 30.0) / 100
    
    # Validar que sume 100% (aprox)
    total = m_h + m_d + m_a
    if abs(total - 1.0) > 0.01:
        st.warning(f"⚠️ Las probabilidades externas suman {total:.1%}. Asegúrate de normalizarlas.")

st.divider()

# CÁLCULO DE VENTAJA (VALUE)
st.subheader("🎯 Análisis de Valor (Edge)")
diff_h = res['home_win'] - m_h
diff_d = res['draw'] - m_d
diff_a = res['away_win'] - m_a

k1, k2, k3 = st.columns(3)
k1.metric("Edge Local", f"{diff_h:+.1%}", delta_color="normal")
k2.metric("Edge Empate", f"{diff_d:+.1%}", delta_color="normal")
k3.metric("Edge Visitante", f"{diff_a:+.1%}", delta_color="normal")

st.info("""
**Interpretación:** Un 'Edge' positivo indica que nuestro modelo ve más probable ese resultado 
que el mercado (posible apuesta de valor).
""")
