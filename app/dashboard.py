import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import DB_PATH

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

from pipeline.database import init_db
init_db()

import streamlit as st
import sqlite3
import pandas as pd

from app.config import DB_PATH
from app.analytics import normalize, performance, volatility, sharpe_ratio
from pipeline.runner import run

# =========================
# Zorg dat data bestaat
# =========================
conn = sqlite3.connect(DB_PATH)

try:
    count = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
except:
    count = 0

conn.close()

if count == 0:
    with st.spinner("Data ophalen..."):
        try:
            run()
        except Exception as e:
            st.error(f"Fout bij ophalen data: {e}")

# =========================
# Dashboard UI
# =========================
st.set_page_config(layout="wide")
st.title("📈 Funds Intelligence Dashboard")

conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("SELECT * FROM prices", conn)
conn.close()

if df.empty:
    st.warning("Geen data beschikbaar")
    st.stop()

# =========================
# Data processing
# =========================
df["date"] = pd.to_datetime(df["date"])
pivot = df.pivot(index="date", columns="fund", values="price")

# =========================
# Filters
# =========================
selected = st.multiselect(
    "Selecteer fondsen",
    pivot.columns,
    default=list(pivot.columns)[:5]
)

if not selected:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

pivot = pivot[selected]

# =========================
# Analyse
# =========================
norm = normalize(pivot)

# =========================
# Visuals
# =========================
st.subheader("📊 Groei (genormaliseerd)")
st.line_chart(norm)

st.subheader("🏆 Performance (%)")
perf = performance(norm)
st.dataframe(perf)

st.subheader("⚡ Volatility")
st.dataframe(volatility(norm))

st.subheader("📉 Sharpe Ratio")
st.dataframe(sharpe_ratio(norm))

# =========================
# Highlight beste fonds
# =========================
if not perf.empty:
    best = perf.index[0]
    st.success(f"🏆 Beste fonds: {best}")
