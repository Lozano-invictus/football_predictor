import streamlit as st
import pandas as pd
from data.database import get_session, Prediction

st.set_page_config(page_title="Historial de Predicciones", page_icon="📜", layout="wide")

st.title("📜 Historial de Predicciones")
st.markdown("""
En esta sección se guardan todas las predicciones generadas por el sistema para su posterior 
análisis de precisión y calibración.
""")

session = get_session()

try:
    # Cargar predicciones con join para nombres de equipos
    query = session.query(
        Prediction.timestamp,
        Prediction.model_used,
        Prediction.prob_home,
        Prediction.prob_draw,
        Prediction.prob_away,
        Prediction.expected_home,
        Prediction.expected_away
    )
    
    # Nota: para simplificar en esta vista, no hacemos el join complejo si no hay muchos datos aún
    # Pero lo ideal es mostrar nombres
    
    predictions = query.order_by(Prediction.timestamp.desc()).all()

    if not predictions:
        st.info("Aún no hay predicciones guardadas en la base de datos.")
        st.info("Las predicciones se guardarán automáticamente cuando realices análisis en la página de 'Partido'.")
    else:
        df = pd.DataFrame([
            {
                "Fecha": p.timestamp.strftime("%Y-%m-%d %H:%M"),
                "Modelo": p.model_used,
                "Prob. Local": f"{p.prob_home:.1%}",
                "Prob. Empate": f"{p.prob_draw:.1%}",
                "Prob. Visitante": f"{p.prob_away:.1%}",
                "xG Local": round(p.expected_home, 2),
                "xG Visitante": round(p.expected_away, 2),
            } for p in predictions
        ])
        
        st.dataframe(df, use_container_width=True)

        if st.button("Limpiar Historial"):
            session.query(Prediction).delete()
            session.commit()
            st.rerun()

except Exception as e:
    st.error(f"Error cargando el historial: {e}")
finally:
    session.close()
