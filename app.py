"""Publica el tablero (salida/index.html) en Streamlit.

La corrida diaria (correr.bat) arma salida/. Esta app solo muestra lo último que haya ahí.
  Local:  streamlit run app.py
  Nube:   subir app.py, requirements.txt, .streamlit/config.toml, salida/index.html y static/ a GitHub
          (antes de cada subida: py app.py  -> copia el logo y las fichas PDF a static/).
Streamlit sirve static/ en /app/static/ (enableStaticServing en .streamlit/config.toml): de ahí salen el logo y los PDF."""
import base64
import shutil
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).parent
SALIDA = RAIZ / "salida"
STATIC = RAIZ / "static"
ALTO = 820  # alto del tablero en px; el tablero se escala solo al ancho y alto disponibles


def sincronizar():
    """Copia el logo y las fichas PDF de salida/ a static/ cuando hay versiones nuevas."""
    for sub in ("img", "fichas"):
        origen = SALIDA / sub
        if not origen.exists():
            continue
        destino = STATIC / sub
        destino.mkdir(parents=True, exist_ok=True)
        for f in origen.iterdir():
            d = destino / f.name
            if f.is_file() and (not d.exists() or f.stat().st_mtime > d.stat().st_mtime):
                shutil.copy2(f, d)


def tablero():
    html = (SALIDA / "index.html").read_text(encoding="utf-8")
    # el logo va incrustado (en Streamlit Cloud la app vive en una subruta y /app/static/ no siempre resuelve)
    logo = next((f for f in (STATIC / "img" / "logo_midagri.png", SALIDA / "img" / "logo_midagri.png") if f.exists()), None)
    if logo:
        html = html.replace('src="img/logo_midagri.png"', 'src="data:image/png;base64,' + base64.b64encode(logo.read_bytes()).decode() + '"')
    # PDF: ruta relativa a la app (sirve en local y en la nube)
    html = html.replace('"fichas/ficha_', '"app/static/fichas/ficha_')
    return html


if __name__ == "__main__" and not st.runtime.exists():
    sincronizar()  # py app.py: solo prepara static/ para subirlo
    print("static/ al día")
else:
    st.set_page_config(page_title="Observatorio de Riesgo Agrícola", layout="wide", initial_sidebar_state="collapsed")
    st.markdown("""<style>
      header[data-testid="stHeader"], footer, #MainMenu { display: none }
      .block-container { padding: 0 !important; max-width: 100% !important }
      iframe { display: block; border: 0 }
    </style>""", unsafe_allow_html=True)
    sincronizar()
    if not (SALIDA / "index.html").exists():
        st.error("Todavía no hay tablero: falta salida/index.html (se genera con correr.bat).")
    else:
        st.components.v1.html(tablero(), height=ALTO, scrolling=False)
