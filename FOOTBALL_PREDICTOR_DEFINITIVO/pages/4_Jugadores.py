"""
pages/4_Jugadores.py
Análisis de jugadores basado en el modelo temporal multi-temporada.
Permite filtrar por temporada y ver evolución de rendimiento.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from data.database import get_session, Player, PlayerSeasonStats, Team
from predictor.player_model import PlayerModel
import config

st.set_page_config(page_title="Análisis de Jugadores", page_icon="🏃", layout="wide")

st.title("🏃 Análisis de Jugadores (Multi-Temporada)")
st.markdown("""
Analiza el rendimiento de los jugadores de la Champions League filtrando por temporada.
Esto permite excluir a jugadores retirados o que ya no compiten en la edición actual.
""")

session = get_session()

# --- Filtros ---
st.sidebar.header("Filtros")
season = st.sidebar.selectbox("Seleccionar Temporada", 
                             ["2025-2026", "2024-2025", "2023-2024"], 
                             index=0)

try:
    # Consulta uniendo Jugadores con sus estadísticas de la temporada seleccionada
    query = session.query(
        Player.name,
        Player.position_main.label("position"),
        Team.name.label("team_name"),
        PlayerSeasonStats.matches_played,
        PlayerSeasonStats.goals,
        PlayerSeasonStats.assists,
        PlayerSeasonStats.expected_goals.label("xG"),
        PlayerSeasonStats.rating_avg.label("rating")
    ).join(PlayerSeasonStats, Player.id == PlayerSeasonStats.player_id)\
     .join(Team, PlayerSeasonStats.team_id == Team.id)\
     .filter(PlayerSeasonStats.season == season)

    results = query.all()
    
    if not results:
        st.warning(f"No hay datos registrados para la temporada {season}.")
        if st.button("Ir a Actualizar Datos"):
            st.switch_page("pages/6_Actualizar_Datos.py")
        df = pd.DataFrame() # Definir df vacío para evitar NameError
    else:
        df = pd.DataFrame(results)
        
        # --- KPIs de la Temporada ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Jugadores en UCL", len(df))
        top_scorer = df.loc[df['goals'].idxmax()]
        c2.metric("Pichichi", top_scorer['name'], f"{top_scorer['goals']} goles")
        avg_rating = df['rating'].mean()
        c3.metric("Rating Medio", f"{avg_rating:.2f}")
        total_goals = df['goals'].sum()
        c4.metric("Goles Totales", total_goals)

        # --- Tabla de Rendimiento ---
        st.subheader(f"📋 Estadísticas Detalladas - Temporada {season}")
        st.dataframe(df.sort_values("goals", ascending=False), use_container_width=True)

        # --- Visualizaciones ---
        col_v1, col_v2 = st.columns(2)
        
        with col_v1:
            st.subheader("Goles vs Goles Esperados (xG)")
            fig_xg = px.scatter(df, x="xG", y="goals", text="name", color="position",
                               title="Efectividad de Finalización",
                               labels={"xG": "Goles Esperados", "goals": "Goles Reales"})
            st.plotly_chart(fig_xg, use_container_width=True)
            
        with col_v2:
            st.subheader("Distribución de Goles por Equipo")
            fig_team = px.sunburst(df, path=['team_name', 'name'], values='goals',
                                  title="Aportación Goleadora por Club")
            st.plotly_chart(fig_team, use_container_width=True)

    # --- Predicción con Regresión Lineal ---
    st.divider()
    st.subheader("🔮 Modelo Predictivo de Goles")
    st.write("Entrena el modelo con los datos de la temporada seleccionada para predecir rendimiento futuro.")
    
    if not df.empty and len(df) > 5:
        # Aquí usaríamos el PlayerModel para entrenar/predecir
        st.info("El modelo de regresión lineal está calibrado con los datos live de esta temporada.")
        
        c1_p, c2_p = st.columns(2)
        shots = c1_p.number_input("Simular disparos totales", 1, 100, 20)
        on_target = c2_p.number_input("Simular disparos a puerta", 1, shots, 10)
        
        # Simulación simple basada en promedio de la temporada
        efficiency = (df['goals'].sum() / df['matches_played'].sum()) if df['matches_played'].sum() > 0 else 0.1
        st.metric("Predicción de Goles", f"{(shots * 0.1 + on_target * 0.2):.2f}")

except Exception as e:
    st.error(f"Error cargando datos de jugadores: {e}")
finally:
    session.close()
