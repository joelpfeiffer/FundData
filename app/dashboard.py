import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import date
from datetime import datetime

st.set_page_config(layout="wide")

import streamlit as st
from supabase_client import (
    supabase,
    supabase_admin
)



if "portfolio_view" not in st.session_state:
                st.session_state.portfolio_view = "week"

if "admin_view" not in st.session_state:

    st.session_state.admin_view = "funds"

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv(CSV_URL)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date","price","fund"])
    return df.sort_values("date")

df = load_data()

if df.empty:
    st.error("Geen data beschikbaar")
    st.stop()

pivot_full = df.pivot(index="date", columns="fund", values="price")
pivot_full = pivot_full.sort_index()


# =========================
# MERGE FONDSNAAMWIJZIGINGEN
# =========================

old_name = "Zwitser­leven Vanguard US 500 Stock Index Fund"
new_name = "Zwitser­leven Vanguard US 500 Hedged"

if old_name in pivot_full.columns and new_name in pivot_full.columns:
    pivot_full[new_name] = pivot_full[new_name].combine_first(
        pivot_full[old_name]
    )

    pivot_full = pivot_full.drop(columns=[old_name])

elif old_name in pivot_full.columns:
    pivot_full = pivot_full.rename(
        columns={old_name: new_name}
    )

if not pivot_full.empty:
    pivot_full = pivot_full.ffill()

# =========================
# SIDEBAR
# =========================
st.sidebar.title("Instellingen")

funds = list(pivot_full.columns)

# Gewenste standaardfondsen
default_funds = [
    "Zwitserleven Europees Aandelenfonds",
    "Zwitserleven Index Aandelenfonds Europa",
    "Zwitserleven Index Aandelenfonds Opkomende Landen",
    "Zwitserleven Wereld Aandelenfonds",
    "Zwitserleven Index Wereld Aandelenfonds"
]

# Zoek Vanguard automatisch op
vanguard_fund = next(
    (
        f for f in funds
        if "Vanguard" in f
        and "500" in f
        and "Hedged" in f
        and "PPI" not in f
    ),
    None
)

if vanguard_fund:
    default_funds.append(vanguard_fund)

# Alleen fondsen selecteren die daadwerkelijk bestaan
found_defaults = [f for f in default_funds if f in funds]

selected = st.sidebar.multiselect(
    "Fondsen",
    funds,
    default=found_defaults,
    key="fonds_selectie_v2"
)

mode = st.sidebar.radio(
    "Timeframe",
    ["Preset", "Custom"]
)

if mode == "Preset":
    tf = st.sidebar.selectbox(
        "Periode",
        ["1W", "2W", "1M", "3M", "6M", "1Y", "ALL"],
        index=6
    )

    days_map = {
        "1W": 7,
        "2W": 14,
        "1M": 30,
        "3M": 90,
        "6M": 180,
        "1Y": 365
    }
else:
    start = st.sidebar.date_input(
        "Start",
        pivot_full.index.min()
    )

    end = st.sidebar.date_input(
        "End",
        pivot_full.index.max()
    )

if not selected:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

#login

st.sidebar.divider()
st.sidebar.subheader("Inloggen")


if not st.session_state.get("logged_in"):

    email = st.sidebar.text_input("E-mail")

    password = st.sidebar.text_input(
        "Wachtwoord",
        type="password"
    )

    if st.sidebar.button("Inloggen"):

        try:

            result = (
                supabase.auth.sign_in_with_password(
                    {
                        "email": email,
                        "password": password
                    }
                )
            )

            profile = (
                supabase
                .table("profiles")
                .select("*")
                .eq(
                    "id",
                    result.user.id
                )
                .single()
                .execute()
            )

            if not profile.data["is_active"]:

                st.error(
                    "Account is geblokkeerd"
                )

                try:
                    supabase.auth.sign_out()
                except Exception:
                    pass

                st.stop()

            st.session_state.logged_in = True
            st.session_state.user_id = result.user.id
            st.session_state.username = profile.data["display_name"]
            st.session_state.role = profile.data["role"]

            (
                supabase
                .table("profiles")
                .update({
                    "last_login":
                        datetime.now().isoformat()
                })
                .eq(
                    "id",
                    result.user.id
                )
                .execute()
            )

            st.rerun()

        except Exception as e:

            st.error("Onjuiste login")
    

else:

    st.sidebar.success(
        f"Ingelogd als "
        f"{st.session_state.username}"
    )

    st.sidebar.write(
        f"Rol: "
        f"{st.session_state.role}"
    )

    if st.sidebar.button("Uitloggen"):

        try:
            supabase.auth.sign_out()
        except Exception:
            pass

        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.role = None

        st.session_state.portfolio_id = None
        st.session_state.portfolio_name = None

        st.rerun()

        
# =========================
# FILTER DATA
# =========================
pivot = pivot_full[selected].copy()

if mode == "Preset" and tf != "ALL":
    cutoff = pivot.index.max() - pd.Timedelta(days=days_map[tf])
    pivot = pivot.loc[pivot.index >= cutoff]
elif mode == "Custom":
    pivot = pivot[(pivot.index >= pd.to_datetime(start)) & (pivot.index <= pd.to_datetime(end))]

pivot = pivot.dropna(how="all")

if len(pivot) < 2:
    st.warning("Te weinig data na filtering")
    st.dataframe(pivot)
    st.stop()

returns = pivot.pct_change().dropna()

if returns.empty:
    st.warning("Te weinig data voor berekeningen")
    st.stop()

# =========================
# CALCULATIONS
# =========================
ret = (pivot.iloc[-1] / pivot.iloc[0] - 1) * 100
vol = returns.std() * np.sqrt(TRADING_DAYS)
sharpe = (returns.mean()*TRADING_DAYS)/vol.replace(0,np.nan)

drawdown = pivot / pivot.cummax() - 1
max_dd = drawdown.min()

# ===== CAGR =====
days = (pivot.index[-1] - pivot.index[0]).days
years = days / 365

if years > 0:
    cagr = ((pivot.iloc[-1] / pivot.iloc[0]) ** (1/years) - 1) * 100
else:
    cagr = pd.Series(index=pivot.columns, dtype=float)

# ===== SORTINO =====
downside = returns.copy()
downside[downside > 0] = 0
downside_std = downside.std() * np.sqrt(TRADING_DAYS)

sortino = (returns.mean()*TRADING_DAYS) / downside_std.replace(0,np.nan)

# =========================
# TABS
# =========================

is_logged_in = (
    st.session_state.get(
        "logged_in",
        False
    )
)

is_admin = (
    st.session_state.get(
        "role"
    )
    == "admin"
)

tab_names = [
    "Overview",
    "Performance",
    "Risk",
    "Heatmap",
    "Optimizer",
    "Rebalance",
    "Raw Data"
]

if is_admin:
    tab_names.append("Admin")

if is_logged_in:
    tab_names.append("Mijn Portefeuille")
    tab_names.append("Analyse")

if is_admin:
    tab_names.append("Test page")


if is_logged_in:
    tab_names.append("RLS debug")


tabs = st.tabs(tab_names)

tab1 = tabs[0]
tab2 = tabs[1]
tab3 = tabs[2]
tab4 = tabs[3]
tab5 = tabs[4]
tab6 = tabs[5]
tab7 = tabs[6]

tab8 = None
tab9 = None
tab10 = None
tab11 = None
tab12 = None

if is_admin and is_logged_in:

    tab8 = tabs[7]
    tab9 = tabs[8]
    tab10 = tabs[9]
    tab11 = tabs[10]
    tab12 = tabs[11]

elif is_admin:

    tab8 = tabs[7]

elif is_logged_in:

    tab9 = tabs[7]
    tab10 = tabs[8]
    tab12 = tabs[9]

# =========================
# OVERVIEW
# =========================
with tab1:
    st.subheader("Overview")

    best = ret.idxmax()
    worst = ret.idxmin()

    c1,c2,c3,c4,c5,c6,c7 = st.columns(7)

    c1.metric("Gem. rendement", f"{ret.mean():.2f}%")
    c2.metric("Beste fonds", best)
    c3.metric("Slechtste fonds", worst)
    c4.metric("Volatiliteit", f"{vol.mean():.2f}")
    c5.metric("Sharpe", f"{sharpe.mean():.2f}")
    c6.metric("CAGR", f"{cagr.mean():.2f}%")
    c7.metric("Sortino", f"{sortino.mean():.2f}")

    if vol.notna().any():
        risico_txt = f"{vol.idxmax()} (volatiliteit {vol.max():.2f})"
    else:
        risico_txt = "Geen volatiliteitsdata"

    st.info(f"""
Beste: {best} (+{ret.max():.2f}%)
Slechtste: {worst} ({ret.min():.2f}%)
Hoogste risico: {risico_txt}
""")

    # ===== PRIJS =====
    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index,y=pivot[col],name=col))
    st.plotly_chart(fig,use_container_width=True)

    # ===== GENORMALISEERD =====
    st.subheader("Genormaliseerde groei (index = 100)")
    norm = pivot / pivot.iloc[0] * 100

    fig2 = go.Figure()
    for col in norm.columns:
        fig2.add_trace(go.Scatter(x=norm.index,y=norm[col],name=col))
    st.plotly_chart(fig2, use_container_width=True)

    # ===== DRAWDOWN =====
    st.subheader("Drawdown")
    fig3 = go.Figure()
    for col in drawdown.columns:
        fig3.add_trace(go.Scatter(x=drawdown.index,y=drawdown[col]*100,name=col))
    st.plotly_chart(fig3, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    st.subheader("Momentum")

    if len(pivot) < 30:
        st.warning("Minimaal 30 dagen data nodig")
    else:
        mom = (pivot / pivot.shift(30) - 1) * 100
        mom_last = mom.iloc[-1].dropna().to_frame(name="Momentum")
        mom_last["Fund"] = mom_last.index
        st.bar_chart(mom_last.set_index("Fund"))

# =========================
# RISK
# =========================
with tab3:
    st.subheader("Risk")

    risk_df = pd.DataFrame({
        "Volatility": vol,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "CAGR %": cagr,
        "Max Drawdown %": max_dd * 100
    })

    st.dataframe(risk_df, use_container_width=True)

    st.subheader("Rolling Volatility")
    if len(returns) >= 30:
        rolling_vol = returns.rolling(30).std() * np.sqrt(TRADING_DAYS)
        fig = go.Figure()
        for col in rolling_vol.columns:
            fig.add_trace(go.Scatter(x=rolling_vol.index,y=rolling_vol[col],name=col))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Correlation")
    corr = returns.corr()
    fig_corr = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=corr.columns,
        y=corr.index,
        colorscale="RdYlGn",
        zmid=0
    ))
    st.plotly_chart(fig_corr, use_container_width=True)

# =========================
# HEATMAP
# =========================
with tab4:
    st.subheader("Heatmap")

    latest = pivot_full.index.max()

    periods = {
        "1D": 1,
        "2D": 2,
        "3D": 3,
        "4D": 4,
        "5D": 5,
        "6D": 6,
        "1W": 7,
        "2W": 14,
        "3W": 21,
        "1M": 30,
        "2M": 60,
        "3M": 90,
        "4M": 120,
        "5M": 150,
        "6M": 180,
        "1Y": 365
    }

    def calc(days):
        cutoff = latest - pd.Timedelta(days=days)

        past = pivot_full[pivot_full.index <= cutoff]

        if past.empty:
            return pd.Series(index=pivot_full.columns)

        return (pivot_full.loc[latest] / past.iloc[-1] - 1) * 100

    heat = pd.DataFrame({
        label: calc(days)
        for label, days in periods.items()
    })

    heat = heat.reindex(selected).dropna(how="all")

    if not heat.empty:

        fig = go.Figure(
            data=go.Heatmap(
                z=heat.values,
                x=heat.columns,
                y=heat.index,

                text=np.round(heat.values, 2),
                texttemplate="%{text:.2f}%",

                colorscale=[
                [0.00, "#c00000"],  # donkerrood
                [0.15, "#ff0000"],  # rood
                [0.35, "#ffc000"],  # oranje
                [0.50, "#fff2cc"],  # lichtgeel (0%)
                [0.65, "#a9d18e"],  # lichtgroen
                [0.85, "#70ad47"],  # groen
                [1.00, "#006100"]   # donkergroen
                ],

                zmin=-5,
                zmax=5,
                zmid=0,

                colorbar=dict(
                    title="Rendement %"
                )
            )
        )

        fig.update_layout(
            height=max(400, len(heat) * 35),
            margin=dict(l=20, r=20, t=40, b=20)
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )
# =========================
# OPTIMIZER
# =========================
with tab5:
    st.subheader("Optimizer (Portfolio Profielen)")

    if returns.shape[1] < 2:
        st.warning("Minimaal 2 fondsen nodig")
        st.stop()

    # =========================
    # DATA
    # =========================
    mean_returns = returns.mean() * TRADING_DAYS
    cov_matrix = returns.cov() * TRADING_DAYS

    num_assets = len(mean_returns)

    results = []
    weights_list = []

    # =========================
    # MONTE CARLO SIMULATIE
    # =========================
    for _ in range(4000):
        weights = np.random.random(num_assets)
        weights /= np.sum(weights)

        port_return = np.dot(weights, mean_returns)
        port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

        if port_vol == 0:
            port_sharpe = 0
        else:
            port_sharpe = port_return / port_vol

        results.append([port_return, port_vol, port_sharpe])
        weights_list.append(weights)

    results = np.array(results)

    # =========================
    # PROFIELEN
    # =========================
    idx_min_risk = np.argmin(results[:,1])
    idx_max_return = np.argmax(results[:,0])
    idx_max_sharpe = np.argmax(results[:,2])
    idx_balanced = np.argsort(results[:,2])[len(results)//2]

    profiles = {
        "Low Risk": idx_min_risk,
        "Balanced": idx_balanced,
        "High Return": idx_max_return,
        "Max Sharpe": idx_max_sharpe
    }

    selected_profile = st.selectbox(
        "Kies risicoprofiel",
        list(profiles.keys()),
        index=3
    )

    selected_idx = profiles[selected_profile]
    selected_weights = weights_list[selected_idx]

    # =========================
    # RESULTAAT TABEL
    # =========================
    st.subheader("Portfolio verdeling")

    df_profile = pd.DataFrame({
        "Fund": mean_returns.index,
        "Weight %": selected_weights * 100
    }).sort_values("Weight %", ascending=False)

    st.dataframe(df_profile, use_container_width=True)

    # =========================
    # HOVER DATA
    # =========================
    hover_text = []

    for w in weights_list:
        txt = "<br>".join([
            f"{fund}: {weight*100:.1f}%"
            for fund, weight in zip(mean_returns.index, w)
        ])
        hover_text.append(txt)

    # =========================
    # EFFICIENT FRONTIER
    # =========================
    st.subheader("Efficient Frontier")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=results[:,1],
        y=results[:,0],
        mode="markers",
        text=hover_text,
        hovertemplate=
            "<b>Portfolio</b><br>" +
            "Return: %{y:.2f}<br>" +
            "Risk: %{x:.2f}<br><br>" +
            "%{text}<extra></extra>",
        marker=dict(
            color=results[:,2],
            colorscale="Viridis",
            showscale=True,
            colorbar=dict(title="Sharpe"),
            size=6
        ),
        name="Portfolios"
    ))

    # =========================
    # HIGHLIGHT SELECTIE
    # =========================
    fig.add_trace(go.Scatter(
        x=[results[selected_idx,1]],
        y=[results[selected_idx,0]],
        mode="markers",
        marker=dict(size=14, color="red"),
        name=selected_profile
    ))

    fig.update_layout(
        xaxis_title="Risico (volatiliteit)",
        yaxis_title="Rendement",
        height=500
    )

    st.plotly_chart(fig, use_container_width=True)

# =========================
# MONTE CARLO
# =========================
with tab6:
    st.subheader("tijdelijk niet beschikbaar - Monte Carlo Simulatie")
#
#    capital = st.number_input("Kapitaal", 100, 1000000, 10000)
#
#    mean = returns.mean().mean()
#    std = returns.std().mean()
#
#    sims = 100
#    days = 100
#
#    paths = []
#    for _ in range(sims):
#        prices = [capital]
#        for _ in range(days):
#            prices.append(prices[-1]*(1+np.random.normal(mean,std)))
#        paths.append(prices)
#
#    fig = go.Figure()
#    for p in paths[:20]:
#        fig.add_trace(go.Scatter(y=p, showlegend=False))
#    st.plotly_chart(fig)

# =========================
# RAW DATA
# =========================
with tab7:
    st.subheader("Raw Data")

    raw = df[df["fund"].isin(selected)].copy()

    if not raw.empty:
        view = st.radio("Weergave", ["Long","Wide"], horizontal=True)

        if view == "Long":
            display = raw.sort_values("date")
        else:
            display = raw.pivot_table(index="date",columns="fund",values="price").sort_index()

        st.dataframe(display, use_container_width=True)

        st.download_button(
            "Download CSV",
            display.to_csv().encode(),
            "fund_data.csv",
            mime="text/csv"
        )
    
    st.divider()

    st.subheader(
        "Koersen op datum"
    )

    selected_price_date = st.date_input(
        "Selecteer datum",
        key="historische_koersdatum"
    )

    try:

        price_rows = []

        for fund in selected:

            if fund not in pivot_full.columns:

                continue

            fund_series = (
                pivot_full[fund]
            )

            fund_series.index = pd.to_datetime(
                fund_series.index
            )

            match = (
                fund_series[
                    fund_series.index.date
                    == selected_price_date
                ]
            )

            if not match.empty:

                price_rows.append(
                    {
                        "Fonds":
                            fund,

                        "Datum":
                            selected_price_date,

                        "Koers":
                            round(
                                float(
                                    match.iloc[0]
                                ),
                                4
                            )
                    }
                )

        if price_rows:

            koers_df = pd.DataFrame(
                price_rows
            )

            st.dataframe(
                koers_df,
                use_container_width=True
            )

        else:

            st.warning(
                "Geen koersen gevonden op deze datum."
            )

    except Exception as e:

        st.error(e)
# =============
# admin
# =============
if tab8 is not None:
    with tab8:

        is_admin = (
            st.session_state.get("role")
            == "admin"
        )

        if not is_admin:

            st.warning(
                "Geen toegang"
            )

            
        else:

            
            col1, col2 = st.columns(2)

            with col1:
                if st.button( 
                    "Fondsbeheer"
                ):

                    st.session_state.admin_view = (
                        "funds"
                    ) 

            with col2:
                if st.button(
                    "Userbeheer"
                ):

                    st.session_state.admin_view = (
                        "users"
                    )


            if (
                st.session_state.admin_view
                == "funds"
            ):
        
                st.subheader("Fondsbeheer")
        
                st.info(
                    "Fondsen worden automatisch uit prices.csv "
                    "gesynchroniseerd."
                )
        
                if st.button("🔄 Synchroniseer fondsen"):
        
                    try:
        
                        fund_names = sorted(
                            df["fund"]
                            .dropna()
                            .unique()
                            .tolist()
                        )
        
                        toegevoegd = 0
        
                        for fund_name in fund_names:
        
                            bestaande = (
                                supabase
                                .table("funds")
                                .select("id")
                                .eq(
                                    "current_name",
                                    fund_name
                                )
                                .execute()
                            )
        
                            if not bestaande.data:
        
                                fund_code = (
                                    fund_name
                                    .upper()
                                    .replace(" ", "_")
                                    .replace("-", "_")
                                )
        
                                (
                                    supabase
                                    .table("funds")
                                    .insert({
                                        "fund_code": fund_code,
                                        "current_name": fund_name,
                                        "is_active": True
                                    })
                                    .execute()
                                )
        
                                toegevoegd += 1
        
                        st.success(
                            f"{toegevoegd} nieuwe fondsen toegevoegd."
                        )
        
                    except Exception as e:
        
                        st.error(e)
        
                # =====================
                # Fondsen tonen
                # =====================
        
                try:
        
                    funds = (
                        supabase
                        .table("funds")
                        .select("*")
                        .order("current_name")
                        .execute()
                    )
        
                    st.subheader("Geregistreerde fondsen")
        
                    if funds.data:
        
                        st.dataframe(
                            funds.data,
                            use_container_width=True
                        )
        
                    else:
        
                        st.info(
                            "Nog geen fondsen geregistreerd."
                        )
        
                except Exception as e:
        
                    st.error(e)
        
                # =====================
                # Aliasbeheer
                # =====================
        
                st.divider()
        
                st.subheader("Aliasbeheer")
        
                try:
        
                    funds = (
                        supabase
                        .table("funds")
                        .select("*")
                        .eq("is_active", True)
                        .order("current_name")
                        .execute()
                    )
        
                    fund_names = [
                        f["current_name"]
                        for f in funds.data
                    ]
        
                    alias_name = st.selectbox(
                        "Oude naam (alias)",
                        options=fund_names,
                        key="alias_fund"
                    )
        
                    canonical_name = st.selectbox(
                        "Huidige naam (hoofdfonds)",
                        options=fund_names,
                        key="canonical_fund"
                    )
        
                    if st.button("Alias koppelen"):
        
                        if alias_name == canonical_name:
        
                            st.warning(
                                "Alias en hoofdfonds mogen niet gelijk zijn."
                            )
        
                        else:
        
                            canonical_fund = next(
                                f for f in funds.data
                                if f["current_name"] == canonical_name
                            )
        
                            (
                                supabase
                                .table("fund_aliases")
                                .insert({
                                    "fund_id": canonical_fund["id"],
                                    "fund_name": alias_name
                                })
                                .execute()
                            )
        
                            st.success(
                                f"{alias_name} gekoppeld aan {canonical_name}"
                            )
        
                except Exception as e:
        
                    st.error(e)
        
                # =====================
                # Alias overzicht
                # =====================
        
                try:
        
                    aliases = (
                        supabase
                        .table("fund_aliases")
                        .select("*")
                        .execute()
                    )
        
                    st.subheader("Bestaande alias koppelingen")
        
                    if aliases.data:
        
                        st.dataframe(
                            aliases.data,
                            use_container_width=True
                        )
        
                    else:
        
                        st.info(
                            "Nog geen alias koppelingen aanwezig."
                        )
        
                except Exception as e:
        
                    st.error(e)
        
        
            # =====================
            # Controle
            # =====================
        
        
                    st.subheader("Controle")
        
                try:
        
                    fund_count = (
                        supabase
                        .table("funds")
                        .select(
                            "id",
                            count="exact"
                        )
                        .execute()
                    )
        
                    alias_count = (
                        supabase
                        .table("fund_aliases")
                        .select(
                            "id",
                            count="exact"
                        )
                        .execute()
                    )
        
                    col1, col2 = st.columns(2)
        
                    with col1:
                        st.metric(
                            "Aantal fondsen",
                            fund_count.count
                        )
        
                    with col2:
                        st.metric(
                            "Aantal aliases",
                            alias_count.count
                        )
        
                except Exception as e:
        
                    st.error(e)
        
            elif (
                st.session_state.admin_view
                == "users"
                ):
        
                st.subheader(
                    "Userbeheer"
                )

                if st.session_state.role == "admin":

                    profiles = (
                        supabase_admin
                        .table("profiles")
                        .select("*")
                        .order("display_name")
                        .execute()
                    )
                    
                user_df = pd.DataFrame(
                    profiles.data
                )
        
                user_df = user_df.rename(
                    columns={
                        "display_name": "Naam",
                        "role": "Rol",
                        "is_active": "Actief",
                        "last_login": "Laatste login"
                    }
                )
        
                st.dataframe(
                    user_df[
                        [
                            "Naam",
                            "Rol",
                            "Actief",
                            "Laatste login"
                        ]
                    ],
                    use_container_width=True
                )
                user_names = [
                    p["display_name"]
                    for p in profiles.data
                ]
        
                selected_user = st.selectbox(
                    "Gebruiker",
                    user_names
                )
                selected_profile = next(
                    p for p in profiles.data
                    if p["display_name"] == selected_user
                )
        
                st.write(
                    f"Rol: {selected_profile['role']}"
                )
        
                st.write(
                    f"Actief: {selected_profile['is_active']}"
                )
        
                if selected_profile["role"] == "admin":
        
                    st.warning(
                        "Admin accounts kunnen niet geblokkeerd worden."
                    )
        
                else:
        
                    if selected_profile["is_active"]:
        
                        if st.button(
                            "Gebruiker blokkeren"
                        ):
        
                            (
                                supabase
                                .table("profiles")
                                .update({
                                    "is_active": False
                                })
                                .eq(
                                    "id",
                                    selected_profile["id"]
                                )
                                .execute()
                            )
        
                            st.success(
                                "Gebruiker geblokkeerd"
                            )
        
                            st.rerun()
        
                    else:
        
                        if st.button(
                            "Gebruiker deblokkeren"
                        ):
        
                            (
                                supabase
                                .table("profiles")
                                .update({
                                    "is_active": True
                                })
                                .eq(
                                    "id",
                                    selected_profile["id"]
                                )
                                .execute()
                            )
        
                            st.success(
                                "Gebruiker geactiveerd"
                            )
        
                            st.rerun()

                st.divider()

                st.subheader(
                    "Wachtwoord wijzigen"
                )

                new_password = st.text_input(
                    "Nieuw wachtwoord",
                    type="password",
                    key="admin_password_reset"
                )

                if st.button(
                    "Wachtwoord opslaan"
                ):

                    if len(new_password) < 8:

                        st.warning(
                            "Gebruik minimaal 8 tekens."
                        )

                    else:

                        try:

                            supabase_admin.auth.admin.update_user_by_id(
                                selected_profile["id"],
                                {
                                    "password":
                                        new_password
                                }
                            )

                            st.success(
                                f"Wachtwoord gewijzigd voor "
                                f"{selected_profile['display_name']}"
                            )

                        except Exception as e:

                            st.error(e)
                st.divider()
               
        
                st.subheader(
                    "Gebruiker uitnodigen"
                )
        
                with st.form(
                    "invite_user"
                ):
        
                    invite_email = st.text_input(
                        "E-mail"
                    )
        
                    invite_name = st.text_input(
                        "Naam"
                    )
        
                    invite_role = st.selectbox(
                        "Rol",
                        [
                            "user",
                            "admin"
                        ]
                    )
        
                    submit_invite = st.form_submit_button(
                        "Uitnodigen"
                    )
        
                if submit_invite:
        
                    try:
        
                        supabase_admin.auth.admin.invite_user_by_email(
                            invite_email,
                            {
                                "data": {
                                    "display_name":
                                        invite_name,
        
                                    "role":
                                        invite_role
                                }
                            }
                        )
        
                        st.success(
                            f"Uitnodiging verstuurd naar "
                            f"{invite_email}"
                        )
        
                    except Exception as e:
        
                        st.error(e)

# ==================
# Mijn Portefeuille
# ==================
if tab9 is not None:
    with tab9:

        if not st.session_state.get("logged_in"):

            st.warning(
                "Log in om deze pagina te gebruiken."
            )

        else:

            st.success(
                f"Ingelogd als "
                f"{st.session_state.username}"
            )

            st.header("Mijn Portefeuille")

            # Session state
            if "portfolio_id" not in st.session_state:
                st.session_state.portfolio_id = None

            if "portfolio_name" not in st.session_state:
                st.session_state.portfolio_name = None

            if "new_portfolio" not in st.session_state:
                st.session_state.new_portfolio = False

            # -------------------------
            # Portfolio's ophalen
            # -------------------------

            try:

                portfolios = (
                    supabase
                    .table("portfolios")
                    .select("*")
                    .eq(
                        "user_id",
                        st.session_state.user_id
                    )
                    .execute()
                )

                portfolio_options = {
                    p["name"]: p["id"]
                    for p in portfolios.data
                }

            except Exception as e:

                st.error(f"Fout bij ophalen portfolio's: {e}")

                portfolio_options = {}

            # -------------------------
            # Portfolio kiezen
            # -------------------------

            col1, col2, col3 = st.columns([6, 1, 1])

            with col1:

                if portfolio_options:

                    selected_portfolio = st.selectbox(
                        "Bestaande portefeuille",
                        options=list(portfolio_options.keys())
                    )

                else:

                    selected_portfolio = None

                    st.info("Nog geen portfolio's aanwezig")

            with col2:

                st.write("")
                st.write("")

                if (
                    selected_portfolio
                    and st.button("📂 Open", use_container_width=True)
                ):

                    st.session_state.portfolio_id = (
                        portfolio_options[selected_portfolio]
                    )

                    st.session_state.portfolio_name = (
                        selected_portfolio
                    )

                    st.rerun()

            with col3:

                st.write("")
                st.write("")

                if st.button(
                    "➕ Nieuw",
                    use_container_width=True
                ):

                    st.session_state.new_portfolio = True

            # -------------------------
            # Nieuwe portfolio
            # -------------------------

            if st.session_state.new_portfolio:

                st.divider()

                st.subheader("Nieuwe portefeuille")

                new_name = st.text_input(
                    "Naam portefeuille"
                )

                if st.button("Opslaan Nieuwe Portfolio"):

                    try:

                        st.write(
                            "Ingelogde gebruiker:",
                            st.session_state.user_id
                        )

                        result = (
                            supabase
                            .table("portfolios")
                            .insert({
                                "user_id": st.session_state.user_id,
                                "name": new_name,
                                "is_active": True
                            })
                            .execute()
                        )

                        st.write(
                            "Insert resultaat:"
                        )

                        st.write(result)

                        st.success(
                            "Portfolio opgeslagen"
                        )

                        st.session_state.new_portfolio = False

                        st.rerun()

                    except Exception as e:

                        st.error(e)

                        st.write(
                            "user_id:",
                            st.session_state.get(
                                "user_id"
                            )
                        )

            # -------------------------
            # Portfolio geopend
            # -------------------------

            if st.session_state.portfolio_id:

                
                st.success(
                    f"Geopende portefeuille: "
                    f"{st.session_state.portfolio_name}"
                )


                
                st.divider()

                

                col1, col2, col3, col4, col5, col6 = st.columns(6)

                with col1:

                    if st.button("📅 Weeksnapshot"):

                        st.session_state.portfolio_view = "week"

                with col2:

                    if st.button("📈 Maandinvoer"):

                        st.session_state.portfolio_view = "month"

                with col3:

                    if st.button("🎯 Jaarstart"):

                        st.session_state.portfolio_view = "year"

                with col4:

                    if st.button("🗂️ Fondsen"):

                        st.session_state.portfolio_view = "funds"

                with col5:

                    if st.button("📚 Historical data invoer"):

                        st.session_state.portfolio_view = "historical"

                with col6:

                    if st.button("🗄️ Alle data"):

                        st.session_state.portfolio_view = "all_data"


                st.write(
                    f"Geselecteerd scherm: "
                    f"{st.session_state.portfolio_view}"
                )
                

                st.divider()

                if st.session_state.portfolio_view == "funds":
                        
                    st.subheader("Fondsen in portefeuille")

                    try:

                        portfolio_funds = (
                            supabase
                            .table("portfolio_funds")
                            .select("fund_id")
                            .eq(
                                "portfolio_id",
                                st.session_state.portfolio_id
                            )
                            .execute()
                        )

                        linked_fund_ids = {
                            x["fund_id"]
                            for x in portfolio_funds.data
                        }

                        funds = (
                            supabase
                            .table("funds")
                            .select("*")
                            .eq("is_active", True)
                            .order("current_name")
                            .execute()
                        )

                        current_funds = [
                            f for f in funds.data
                            if f["id"] in linked_fund_ids
                        ]

                        if current_funds:

                            for fund in current_funds:

                                st.write(
                                    f"✓ {fund['current_name']}"
                                )

                        else:

                            st.info(
                                "Nog geen fondsen gekoppeld."
                            )

                        st.divider()

                        available_funds = [
                            f for f in funds.data
                            if f["id"] not in linked_fund_ids
                        ]

                        if available_funds:

                            fund_lookup = {
                                f["current_name"]: f["id"]
                                for f in available_funds
                            }

                            selected_fund = st.selectbox(
                                "Nieuw fonds toevoegen",
                                options=list(
                                    fund_lookup.keys()
                                )
                            )

                            if st.button(
                                "Fonds toevoegen"
                            ):

                                (
                                    supabase
                                    .table("portfolio_funds")
                                    .insert({
                                        "portfolio_id":
                                            st.session_state.portfolio_id,
                                        "fund_id":
                                            fund_lookup[selected_fund]
                                    })
                                    .execute()
                                )

                                st.success(
                                    f"{selected_fund} toegevoegd"
                                )

                                st.rerun()

                    except Exception as e:

                        st.error(e)
                
                    
                if st.session_state.portfolio_view == "year":
                
                    # =====================
                    # Jaarstart
                    # =====================

                    st.subheader("Jaarstart")

                    jaar = st.number_input(
                        "Jaar",
                        min_value=2020,
                        max_value=2100,
                        value=2026
                    )

                    startwaarde = st.number_input(
                        "Startwaarde (€)",
                        min_value=0.0,
                        value=25000.0,
                        step=100.0
                    )

                    if st.button("Opslaan Jaarstart"):

                        try:

                            (
                                supabase
                                .table("year_baselines")
                                .insert({
                                    "portfolio_id":
                                        st.session_state.portfolio_id,
                                    "year":
                                        int(jaar),
                                    "start_value":
                                        float(startwaarde),
                                    "version":
                                        1,
                                    "is_active":
                                        True
                                })
                                .execute()
                            )

                            st.success(
                                "Jaarstart opgeslagen"
                            )

                        except Exception as e:

                            st.error(e)

                if st.session_state.portfolio_view == "month":
                    # =====================
                    # Maandsnapshot
                    # =====================

                    st.divider()

                    st.subheader("Maandsnapshot")

                    col1, col2 = st.columns(2)

                    with col1:

                        snapshot_year = st.number_input(
                            "Jaar",
                            min_value=2020,
                            max_value=2100,
                            value=2026,
                            key="snapshot_year"
                        )

                    with col2:

                        snapshot_month = st.selectbox(
                            "Maand",
                            [
                                "Januari",
                                "Februari",
                                "Maart",
                                "April",
                                "Mei",
                                "Juni",
                                "Juli",
                                "Augustus",
                                "September",
                                "Oktober",
                                "November",
                                "December"
                            ]
                        )

                    employer_contribution = st.number_input(
                        "Werkgeverspremie (€)",
                        min_value=0.0,
                        value=0.0,
                        step=10.0
                    )

                    personal_contribution = st.number_input(
                        "Eigen inleg (€)",
                        min_value=0.0,
                        value=0.0,
                        step=10.0
                    )

                    bonus_total = st.number_input(
                        "Bonus totaal YTD (€)",
                        min_value=0.0,
                        value=0.0,
                        step=1.0
                    )

                    costs_total = st.number_input(
                        "Kosten totaal YTD (€)",
                        min_value=0.0,
                        value=0.0,
                        step=1.0
                    )

                    st.divider()

                    st.subheader("Fondsposities")

                    try:

                        portfolio_funds = (
                            supabase
                            .table("portfolio_funds")
                            .select("fund_id")
                            .eq(
                                "portfolio_id",
                                st.session_state.portfolio_id
                            )
                            .execute()
                        )

                        linked_fund_ids = {
                            x["fund_id"]
                            for x in portfolio_funds.data
                        }

                        funds = (
                            supabase
                            .table("funds")
                            .select("*")
                            .eq("is_active", True)
                            .order("current_name")
                            .execute()
                        )

                        active_funds = [
                            f for f in funds.data
                            if f["id"] in linked_fund_ids
                        ]

                        fund_units = {}

                        for fund in active_funds:

                            fund_units[fund["id"]] = st.number_input(
                                fund["current_name"],
                                min_value=0.0,
                                value=0.0,
                                step=0.000001,
                                format="%.6f",
                                key=f"snapshot_fund_{fund['id']}"
                            )

                    except Exception as e:

                        st.error(e)

                    month_map = {
                        "Januari": 1,
                        "Februari": 2,
                        "Maart": 3,
                        "April": 4,
                        "Mei": 5,
                        "Juni": 6,
                        "Juli": 7,
                        "Augustus": 8,
                        "September": 9,
                        "Oktober": 10,
                        "November": 11,
                        "December": 12
                    }

                    snapshot_date = (
                        f"{snapshot_year}-"
                        f"{month_map[snapshot_month]:02d}-01"
                    )

                    existing_snapshot = (
                        supabase
                        .table("monthly_snapshots")
                        .select("*")
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .eq(
                            "snapshot_date",
                            snapshot_date
                        )
                        .eq(
                            "is_active",
                            True
                        )
                        .execute()
                    )

                    if existing_snapshot.data:

                        st.info(
                            "Snapshot bestaat al en kan later "
                            "worden bijgewerkt."
                        )

                    else:

                        st.success(
                            "Nieuwe snapshot."
                        )

                    snapshot_version_note = st.text_input(
                        "Versienotitie",
                        placeholder="Bijv. correctie bonus pensioenfonds"
                    )
                    if st.button("Opslaan Maandsnapshot"):

                        try:

                            month_map = {
                                "Januari": 1,
                                "Februari": 2,
                                "Maart": 3,
                                "April": 4,
                                "Mei": 5,
                                "Juni": 6,
                                "Juli": 7,
                                "Augustus": 8,
                                "September": 9,
                                "Oktober": 10,
                                "November": 11,
                                "December": 12
                            }

                            snapshot_date = (
                                f"{snapshot_year}-"
                                f"{month_map[snapshot_month]:02d}-01"
                            )

                            if existing_snapshot.data:

                                current_snapshot = (
                                    existing_snapshot.data[0]
                                )

                                (
                                    supabase
                                    .table("monthly_snapshots")
                                    .update({
                                        "is_active": False
                                    })
                                    .eq(
                                        "id",
                                        current_snapshot["id"]
                                    )
                                    .execute()
                                )

                                new_version = (
                                    current_snapshot["version"] + 1
                                )

                                snapshot_result = (
                                    supabase
                                    .table("monthly_snapshots")
                                    .insert({
                                        "portfolio_id":
                                            st.session_state.portfolio_id,

                                        "snapshot_date":
                                            snapshot_date,

                                        "employer_contribution":
                                            float(employer_contribution),

                                        "personal_contribution":
                                            float(personal_contribution),

                                        "bonus_total":
                                            float(bonus_total),

                                        "costs_total":
                                            float(costs_total),

                                        "version":
                                            new_version,

                                        "is_active":
                                            True,

                                        "snapshot_version_note":
                                            snapshot_version_note,
                
                                        "created_by":
                                            st.session_state.get(
                                                "username",
                                                "system"
                                            )
                                    })
                                    .execute()
                                )

                                snapshot_id = (
                                    snapshot_result.data[0]["id"]
                                )

                                for fund_id, units in fund_units.items():

                                    if units > 0:

                                        (
                                            supabase
                                            .table("snapshot_positions")
                                            .insert({
                                                "snapshot_id":
                                                    snapshot_id,

                                                "fund_id":
                                                    fund_id,

                                                "units":
                                                    float(units),

                                                "created_by":
                                                    st.session_state.get(
                                                        "username",
                                                        "system"
                                                    )
                                            })
                                            .execute()
                                        )

                                st.success(
                                    f"Nieuwe versie {new_version} opgeslagen"
                                )

                            else:

                                snapshot_result = (
                                    supabase
                                    .table("monthly_snapshots")
                                    .insert({
                                        "portfolio_id":
                                            st.session_state.portfolio_id,

                                        "snapshot_date":
                                            snapshot_date,

                                        "employer_contribution":
                                            float(employer_contribution),

                                        "personal_contribution":
                                            float(personal_contribution),

                                        "bonus_total":
                                            float(bonus_total),

                                        "costs_total":
                                            float(costs_total),

                                        "version":
                                            1,

                                        "is_active":
                                            True,

                                        "snapshot_version_note":
                                            snapshot_version_note,
                
                                        "created_by":
                                            st.session_state.get(
                                                "username",
                                                "system"
                                            )
                                    })
                                    .execute()
                                )

                                snapshot_id = (
                                    snapshot_result.data[0]["id"]
                                )
                                
                                for fund_id, units in fund_units.items():

                                    if units > 0:

                                        (
                                            supabase
                                            .table("snapshot_positions")
                                            .insert({
                                                "snapshot_id":
                                                    snapshot_id,

                                                "fund_id":
                                                    fund_id,

                                                "units":
                                                    float(units),

                                                "created_by":
                                                    st.session_state.get(
                                                        "username",
                                                        "system"
                                                    )
                                            })
                                            .execute()
                                        )
                            
                            st.success(
                                "Maandsnapshot opgeslagen"
                            )

                        except Exception as e:

                            st.error(e)
                    try:

                        show_all_versions = st.checkbox(
                            "Toon alle versies",
                            value=False
                        )
                        portfolio_check = (
                            supabase
                            .table("portfolios")
                            .select("*")
                            .eq(
                                "id",
                                st.session_state.portfolio_id
                            )
                            .execute()
                        )

                        st.write(
                            portfolio_check.data
                        )

                        snapshots_query = (
                            supabase
                            .table("monthly_snapshots")
                            .select("*")
                            .eq(
                                "portfolio_id",
                                st.session_state.portfolio_id
                            )
                        )

                        if not show_all_versions:
                            st.write(
                                "Portfolio ID:",
                                st.session_state.portfolio_id
                            )

                            st.write(
                                "User ID:",
                                st.session_state.user_id
                            )
                            snapshots_query = (
                                snapshots_query
                                .eq(
                                "is_active",
                                    True
                                )
                            )

                        snapshots = (
                            snapshots_query
                            .order(
                                "snapshot_date"
                            )
                            .execute()
                        )

                        st.subheader("Historische snapshots")

                        if snapshots.data:
                            st.dataframe(
                                snapshots.data,
                                use_container_width=True
                            )

                    except Exception as e:

                        st.error(e)
                        
        # ===================
        # weekly
        # ===================
                
                if st.session_state.portfolio_view == "week":
                    st.subheader("weeksnapshot")

                    latest_price_date = (
                        df["date"].max()
                    )

                    st.info(
                        f"Laatste koersdatum: "
                        f"{latest_price_date:%d-%m-%Y}"
                    )
                    latest_snapshot = (
                        supabase
                        .table("monthly_snapshots")
                        .select("*")
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .eq(
                            "is_active",
                            True
                        )
                        .lte(
                            "snapshot_date",
                            str(latest_price_date)
                        )
                        .order(
                            "snapshot_date",
                            desc=True
                        )
                        .limit(1)
                        .execute()
                    )
                    if not latest_snapshot.data:

                        st.warning(
                            "Geen actieve maandsnapshot gevonden."
                        )

                        st.stop()

                    snapshot_id = (
                        latest_snapshot.data[0]["id"]
                    )

                    snapshot_date = pd.to_datetime(
                        latest_snapshot.data[0]["snapshot_date"]
                    ).date()

                    price_date = pd.to_datetime(
                        latest_price_date
                    ).date()

                    if snapshot_date > price_date:

                        st.error(
                            f"Snapshotdatum {snapshot_date} "
                            f"is nieuwer dan koersdatum {price_date}."
                        )

                        st.stop()

                    positions = (
                        supabase
                        .table("snapshot_positions")
                        .select("*")
                        .eq(
                            "snapshot_id",
                            snapshot_id
                        )
                        .execute()
                    )
                    
                    valuation_rows = []
                    
                    for position in positions.data:

                        fund = (
                            supabase
                            .table("funds")
                            .select("current_name")
                            .eq(
                                "id",
                                position["fund_id"]
                            )
                            .single()
                            .execute()
                        )

                        fund_name = (
                            fund.data["current_name"]
                        )

                        units = (
                            position["units"]
                        )

                        price_row = df[
                            (df["fund"] == fund_name)
                            &
                            (df["date"] == latest_price_date)
                        ]

                        if not price_row.empty:

                            price = (
                                float(
                                    price_row.iloc[0]["price"]
                                )
                            )

                            value = (
                                units * price
                            )
                            valuation_rows.append({
                                "fund_id": position["fund_id"],
                                "Fonds": fund_name,
                                "Eenheden": round(units, 6),
                                "Koers": round(price, 4),
                                "Waarde": round(value, 2)
                            })

                            
                        else:

                            st.warning(
                                f"Geen koers gevonden voor "
                                f"{fund_name}"
                            )

                    valuation_df = pd.DataFrame(
                        valuation_rows
                    )

                    st.divider()

                    st.subheader(
                        "Portefeuillewaardering"
                    )

                    st.dataframe(
                        valuation_df,
                        use_container_width=True
                    )

                    total_value = (
                        valuation_df["Waarde"].sum()
                    )

                    st.metric(
                        "Totale portefeuillewaarde",
                        f"€{total_value:,.2f}"
                    )
                    if st.button(
                        "Opslaan waardering"
                    ):
                        try:
                            existing_valuation = (
                                supabase
                                .table("portfolio_valuations")
                                .select("id")
                                .eq(
                                    "portfolio_id",
                                    st.session_state.portfolio_id
                                )
                                .eq(
                                    "valuation_date",
                                    str(date.today())
                                )
                                .execute()
                            )

                            if existing_valuation.data:

                                st.warning(
                                    "Voor vandaag bestaat al een waardering."
                                )

                                st.stop()


                            valuation_result = (
                                supabase
                                .table("portfolio_valuations")
                                .insert({
                                    "portfolio_id":
                                        st.session_state.portfolio_id,

                                    "valuation_date":
                                        str(date.today()),
                                    
                                    "price_date":
                                        str(latest_price_date),

                                    "total_value":
                                        float(total_value)
                                    })
                                .execute()
                            )

                            valuation_id = (
                                valuation_result.data[0]["id"]
                            )

                            for row in valuation_rows:

                                (
                                    supabase
                                    .table("valuation_positions")
                                    .insert({
                                        "valuation_id":
                                            valuation_id,

                                        "fund_id":
                                            row["fund_id"],

                                        "units":
                                            float(row["Eenheden"]),

                                        "price":
                                            float(row["Koers"]),

                                        "value":
                                            float(row["Waarde"]),
                                        "price_date":
                                            str(latest_price_date),

                                        "version":
                                            1,

                                        "is_active":
                                            True,

                                        "created_by":
                                            st.session_state.get(
                                                "username",
                                                "system"
                                            )
                                    })
                                    .execute()
                                )

                            st.success(
                                "Waardering opgeslagen"
                            )

                        except Exception as e:

                            st.error(e)

                    st.success(
                        f"Snapshot gevonden: "
                        f"{latest_snapshot.data[0]['snapshot_date']}"
                    )

                    

                if st.session_state.portfolio_view == "historical":
                
                    st.subheader("Historische invoer")
                    # =====================
                    # Historische invoer
                    # =====================

                    try:

                        snapshots = (
                            supabase
                            .table("monthly_snapshots")
                            .select("*")
                            .eq(
                                "is_active",
                                True
                            )
                            .order(
                                "snapshot_date",
                                desc=True
                            )
                            .execute()
                        )

                        if not snapshots.data:

                            st.warning(
                                "Geen maandelijkse snapshots gevonden."
                            )

                        else:

                            snapshot_options = {
                                str(s["snapshot_date"]): s["id"]
                                for s in snapshots.data
                            }

                            selected_snapshot_date = (
                                st.selectbox(
                                    "Maandsnapshot",
                                    list(snapshot_options.keys())
                                )
                            )

                            selected_date = (
                                st.date_input(
                                    "Koersdatum"
                                )
                            )

                            if st.button(
                                "Bereken historische waarde"
                            ):

                                snapshot_id = (
                                    snapshot_options[
                                        selected_snapshot_date
                                    ]
                                )

                                snapshot_date = (
                                    pd.to_datetime(
                                        selected_snapshot_date
                                    ).date()
                                )

                                if selected_date < snapshot_date:

                                    st.error(
                                        "Koersdatum ligt vóór "
                                        "de snapshotdatum."
                                    )

                                    st.stop()

                                positions = (
                                    supabase
                                    .table(
                                        "snapshot_positions"
                                    )
                                    .select("*")
                                    .eq(
                                        "snapshot_id",
                                        snapshot_id
                                    )
                                    .execute()
                                )

                                valuation_rows = []

                                total_value = 0

                                for position in positions.data:

                                    fund = (
                                        supabase
                                        .table("funds")
                                        .select(
                                            "current_name"
                                        )
                                        .eq(
                                            "id",
                                            position["fund_id"]
                                        )
                                        .single()
                                        .execute()
                                    )

                                    fund_name = (
                                        fund.data[
                                            "current_name"
                                        ]
                                    )

                                    aliases = (
                                        supabase
                                        .table("fund_aliases")
                                        .select("fund_name")
                                        .eq(
                                            "fund_id",
                                            position["fund_id"]
                                        )
                                        .execute()
                                    )

                                    fund_names = [
                                        fund_name
                                    ]

                                    for alias in aliases.data:

                                        fund_names.append(
                                            alias["fund_name"]
                                        )

                                    units = (
                                        position["units"]
                                    )

                                    price_rows = (
                                        df[
                                            (
                                                df["fund"]
                                                .isin(fund_names)
                                            )
                                            &
                                            (
                                                pd.to_datetime(
                                                    df["date"]
                                                ).dt.date
                                                <= selected_date
                                            )
                                        ]
                                        .sort_values(
                                            "date"
                                        )
                                    )


                                    if price_rows.empty:

                                        continue

                                    price_row = (
                                        price_rows
                                        .tail(1)
                                    )

                                    actual_price_date = (
                                        pd.to_datetime(
                                            price_row.iloc[0]["date"]
                                        )
                                        .date()
                                    )

                                    price = float(
                                        price_row.iloc[0]["price"]
                                    )

                                    value = (
                                        units * price
                                    )

                                    total_value += value

                                    valuation_rows.append(
                                        {
                                            "fund_id":
                                                position["fund_id"],

                                            "Fonds":
                                                fund_name,

                                            "Eenheden":
                                                round(
                                                    units,
                                                    6
                                                ),

                                            "Koers":
                                                round(
                                                    price,
                                                    4
                                                ),

                                            "Koersdatum":
                                                actual_price_date,

                                            "Waarde":
                                                round(
                                                    value,
                                                    2
                                                )
                                        }
                                    )

                                if valuation_rows:
                                    st.session_state.historical_rows = (
                                        valuation_rows
                                    )

                                    st.session_state.historical_total = (
                                        total_value
                                    )

                                    st.session_state.historical_date = (
                                        selected_date
                                    )

                                    
                                    valuation_df = (
                                        pd.DataFrame(
                                            valuation_rows
                                        )
                                    )

                                    st.dataframe(
                                        valuation_df,
                                        use_container_width=True
                                    )

                                    st.metric(
                                        "Historische portefeuillewaarde",
                                        f"€{total_value:,.2f}"
                                    )

                            if "historical_rows" in st.session_state:

                                if st.button(
                                    "Historische waardering opslaan"
                                ):

                                    valuation_rows = (
                                        st.session_state.historical_rows
                                    )

                                    total_value = (
                                        st.session_state.historical_total
                                    )

                                    selected_date = (
                                        st.session_state.historical_date
                                    )

                                    existing = (
                                        supabase
                                        .table(
                                            "portfolio_valuations"
                                        )
                                        .select("id")
                                        .eq(
                                            "portfolio_id",
                                            st.session_state.portfolio_id
                                        )
                                        .eq(
                                            "valuation_date",
                                            str(selected_date)
                                        )
                                        .execute()
                                    )

                                    if existing.data:

                                        st.warning(
                                            "Voor deze datum bestaat al een waardering."
                                        )

                                    else:

                                        try:
                                            
                                            
                                            valuation_result = (
                                                supabase
                                                .table(
                                                    "portfolio_valuations"
                                                )
                                                .insert({
                                                    "portfolio_id":
                                                        st.session_state.portfolio_id,

                                                    "valuation_date":
                                                        str(selected_date),

                                                    "price_date":
                                                        str(selected_date),

                                                    "total_value":
                                                        float(total_value)
                                                })
                                                .execute()
                                            )

                                            valuation_id = (
                                                valuation_result.data[0]["id"]
                                            )
                                            

                                            for row in valuation_rows:

                                                (
                                                    supabase
                                                    .table(
                                                        "valuation_positions"
                                                    )
                                                    .insert({
                                                        "valuation_id":
                                                            valuation_id,

                                                        "fund_id":
                                                            row["fund_id"],

                                                        "units":
                                                            float(
                                                                row["Eenheden"]
                                                            ),

                                                        "price":
                                                            float(
                                                                row["Koers"]
                                                            ),

                                                        "value":
                                                            float(
                                                                row["Waarde"]
                                                            ),

                                                        "price_date":
                                                            str(
                                                                row["Koersdatum"]
                                                            ),

                                                        "version":
                                                            1,

                                                        "is_active":
                                                            True,

                                                        "created_by":
                                                            st.session_state.get(
                                                                "username",
                                                                "system"
                                                            )
                                                    })
                                                    .execute()
                                                )

                                            st.success(
                                                "Historische waardering opgeslagen."
                                            )

                                        except Exception as e:

                                            st.error(e)


                                else:

                                    st.warning(
                                        "Geen historische "
                                        "koersen gevonden."
                                    )

                    except Exception as e:

                        st.error(e)

                    st.divider()

                    st.subheader(
                        "Historische waarde direct invoeren"
                    )

                    manual_date = st.date_input(
                        "Waarderingsdatum",
                        key="manual_valuation_date"
                    )

                    fund_values = {}

                    st.markdown(
                        "Voer per fonds de totale waarde in."
                    )

                    for fund_name in selected:

                        fund_values[fund_name] = st.number_input(
                            fund_name,
                            min_value=0.0,
                            value=0.0,
                            step=100.0,
                            format="%.2f",
                            key=f"manual_value_{fund_name}"
                        )

                    total_value = sum(
                        fund_values.values()
                    )

                    st.metric(
                        "Totale portefeuillewaarde",
                        f"€ {total_value:,.2f}"
                    )

                    if st.button(
                        "Historische waarde opslaan"
                    ):

                        try:

                            existing = (
                                supabase
                                .table(
                                    "portfolio_valuations"
                                )
                                .select("id")
                                .eq(
                                    "portfolio_id",
                                    st.session_state.portfolio_id
                                )
                                .eq(
                                    "valuation_date",
                                    str(manual_date)
                                )
                                .execute()
                            )

                            if existing.data:

                                st.warning(
                                    "Voor deze datum bestaat al een waardering."
                                )

                            else:

                                valuation_result = (
                                    supabase
                                    .table(
                                        "portfolio_valuations"
                                    )
                                    .insert({
                                        "portfolio_id":
                                            st.session_state.portfolio_id,

                                        "valuation_date":
                                            str(manual_date),

                                        "price_date":
                                            str(manual_date),

                                        "total_value":
                                            float(total_value)
                                    })
                                    .execute()
                                )

                                valuation_id = (
                                    valuation_result.data[0]["id"]
                                )

                                funds_lookup = (
                                    supabase
                                    .table(
                                        "funds"
                                    )
                                    .select(
                                        "id,current_name"
                                    )
                                    .execute()
                                )

                                fund_map = {
                                    row["current_name"]: row["id"]
                                    for row in funds_lookup.data
                                }

                                for fund_name, value in fund_values.items():

                                    if value <= 0:

                                        continue

                                    if fund_name not in fund_map:

                                        continue

                                    (
                                        supabase
                                        .table(
                                            "valuation_positions"
                                        )
                                        .insert({
                                            "valuation_id":
                                                valuation_id,

                                            "fund_id":
                                                fund_map[fund_name],

                                            "units":
                                                0,

                                            "price":
                                                0,

                                            "value":
                                                float(value),

                                            "price_date":
                                                str(manual_date),

                                            "version":
                                                1,

                                            "is_active":
                                                True,

                                            "created_by":
                                                st.session_state.get(
                                                    "username",
                                                    "system"
                                                )
                                        })
                                        .execute()
                                    )

                                st.success(
                                    "Historische waardering opgeslagen."
                                )

                                st.rerun()

                        except Exception as e:

                            st.error(e)

                if st.session_state.portfolio_view == "all_data":
                
                    # =====================
                    # alle data
                    # =====================

                    st.subheader("Alle Data")

                    st.header("Portfolio Beheer")

                    try:

                        portfolios = (
                            supabase
                            .table("portfolios")
                            .select("*")
                            .eq(
                                "user_id",
                                st.session_state.user_id
                            )
                            .order("name")
                            .execute()
                        )

                        if not portfolios.data:

                            st.info(
                                "Geen portfolio's gevonden"
                            )

                            st.stop()

                        portfolio_options = {
                            p["name"]: p["id"]
                            for p in portfolios.data
                        }

                        selected_portfolio_name = st.selectbox(
                            "Selecteer Portfolio",
                            list(
                                portfolio_options.keys()
                            )
                        )

                        selected_portfolio_id = (
                            portfolio_options[
                                selected_portfolio_name
                            ]
                        )

                        st.success(
                            f"Geselecteerd: "
                            f"{selected_portfolio_name}"
                        )

                        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                            "Portfolio Funds",
                            "Monthly Snapshots",
                            "Snapshot Positions",
                            "Portfolio Valuations",
                            "Valuation Positions",
                            "Year Baselines"
                        ])

                        # ==========================
                        # Portfolio Funds
                        # ==========================

                        with tab1:

                            rows = (
                                supabase
                                .table("portfolio_funds")
                                .select("*")
                                .eq(
                                    "portfolio_id",
                                    selected_portfolio_id
                                )
                                .execute()
                            )

                            if not rows.data:

                                st.info(
                                    "Geen portfolio funds gevonden"
                                )

                            else:

                                funds_df = pd.DataFrame(
                                    rows.data
                                )

                                funds_df[
                                    "Verwijderen"
                                ] = False

                                edited_df = st.data_editor(
                                    funds_df,
                                    use_container_width=True,
                                    hide_index=True,
                                    disabled=[
                                        col
                                        for col in funds_df.columns
                                        if col != "Verwijderen"
                                    ]
                                )

                                delete_ids = (
                                    edited_df[
                                        edited_df[
                                            "Verwijderen"
                                        ]
                                    ]["id"]
                                    .tolist()
                                )

                                if delete_ids:

                                    st.warning(
                                        f"{len(delete_ids)} record(s) geselecteerd voor verwijdering"
                                    )

                                    if st.button(
                                        "Verwijder geselecteerde portfolio funds",
                                        type="primary"
                                    ):

                                        deleted = 0

                                        for record_id in delete_ids:

                                            try:

                                                (
                                                    supabase
                                                    .table(
                                                        "portfolio_funds"
                                                    )
                                                    .delete()
                                                    .eq(
                                                        "id",
                                                        record_id
                                                    )
                                                    .execute()
                                                )

                                                deleted += 1

                                            except Exception as e:

                                                st.error(
                                                    f"Fout bij verwijderen van ID {record_id}: {e}"
                                                )

                                        st.success(
                                            f"{deleted} portfolio fund(s) verwijderd"
                                        )

                                        st.rerun()
                        # ==========================
                        # Monthly Snapshots
                        # ==========================

                        with tab2:

                            rows = (
                                supabase
                                .table("monthly_snapshots")
                                .select("*")
                                .eq(
                                    "portfolio_id",
                                    selected_portfolio_id
                                )
                                .order(
                                    "snapshot_date",
                                    desc=True
                                )
                                .execute()
                            )

                            if not rows.data:

                                st.info(
                                    "Geen snapshots gevonden"
                                )

                            else:

                                snapshots_df = pd.DataFrame(
                                    rows.data
                                )

                                snapshots_df[
                                    "Verwijderen"
                                ] = False

                                edited_df = st.data_editor(
                                    snapshots_df,
                                    use_container_width=True,
                                    hide_index=True,
                                    disabled=[
                                        col
                                        for col in snapshots_df.columns
                                        if col != "Verwijderen"
                                    ]
                                )

                                delete_ids = (
                                    edited_df[
                                        edited_df["Verwijderen"]
                                    ]["id"]
                                    .tolist()
                                )

                                st.info(
                                    f"{len(delete_ids)} snapshot(s) geselecteerd"
                                )

                                confirm_delete = st.checkbox(
                                    "Ik weet zeker dat ik deze snapshots wil verwijderen",
                                    key="confirm_delete_snapshots"
                                )

                                if (
                                    len(delete_ids) > 0
                                    and confirm_delete
                                ):

                                    if st.button(
                                        "Verwijder geselecteerde snapshots",
                                        type="primary",
                                        key="delete_snapshots_button"
                                    ):

                                        deleted = 0

                                        for snapshot_id in delete_ids:

                                            try:

                                                # Eerst child records verwijderen

                                                (
                                                    supabase
                                                    .table(
                                                        "snapshot_positions"
                                                    )
                                                    .delete()
                                                    .eq(
                                                        "snapshot_id",
                                                        snapshot_id
                                                    )
                                                    .execute()
                                                )

                                                # Daarna snapshot verwijderen

                                                (
                                                    supabase
                                                    .table(
                                                        "monthly_snapshots"
                                                    )
                                                    .delete()
                                                    .eq(
                                                        "id",
                                                        snapshot_id
                                                    )
                                                    .execute()
                                                )

                                                deleted += 1

                                            except Exception as e:

                                                st.error(
                                                    f"Fout bij snapshot {snapshot_id}: {e}"
                                                )

                                        st.success(
                                            f"{deleted} snapshot(s) verwijderd"
                                        )

                                        st.rerun()

                        # ==========================
                        # Snapshot Positions
                        # ==========================

                        with tab3:

                            snapshots = (
                                supabase
                                .table("monthly_snapshots")
                                .select("id")
                                .eq(
                                    "portfolio_id",
                                    selected_portfolio_id
                                )
                                .execute()
                            )

                            snapshot_ids = [
                                row["id"]
                                for row in snapshots.data
                            ]

                            if not snapshot_ids:

                                st.info(
                                    "Geen snapshots gevonden"
                                )

                            else:

                                rows = (
                                    supabase
                                    .table("snapshot_positions")
                                    .select("*")
                                    .in_(
                                        "snapshot_id",
                                        snapshot_ids
                                    )
                                    .execute()
                                )

                                if not rows.data:

                                    st.info(
                                        "Geen snapshot positions gevonden"
                                    )

                                else:

                                    positions_df = pd.DataFrame(
                                        rows.data
                                    )

                                    positions_df[
                                        "Verwijderen"
                                    ] = False

                                    edited_df = st.data_editor(
                                        positions_df,
                                        use_container_width=True,
                                        hide_index=True,
                                        disabled=[
                                            col
                                            for col in positions_df.columns
                                            if col != "Verwijderen"
                                        ]
                                    )

                                    delete_ids = (
                                        edited_df[
                                            edited_df["Verwijderen"]
                                        ]["id"]
                                        .tolist()
                                    )

                                    st.info(
                                        f"{len(delete_ids)} positie(s) geselecteerd"
                                    )

                                    confirm_delete = st.checkbox(
                                        "Ik weet zeker dat ik deze posities wil verwijderen",
                                        key="confirm_delete_snapshot_positions"
                                    )

                                    if (
                                        len(delete_ids) > 0
                                        and confirm_delete
                                    ):

                                        if st.button(
                                            "Verwijder geselecteerde posities",
                                            type="primary",
                                            key="delete_snapshot_positions_button"
                                        ):

                                            deleted = 0

                                            for position_id in delete_ids:

                                                try:

                                                    (
                                                        supabase
                                                        .table(
                                                            "snapshot_positions"
                                                        )
                                                        .delete()
                                                        .eq(
                                                            "id",
                                                            position_id
                                                        )
                                                        .execute()
                                                    )

                                                    deleted += 1

                                                except Exception as e:

                                                    st.error(
                                                        f"Fout bij positie {position_id}: {e}"
                                                    )

                                            st.success(
                                                f"{deleted} positie(s) verwijderd"
                                            )

                                            st.rerun()

                        # ==========================
                        # Portfolio Valuations
                        # ==========================

                        with tab4:

                            rows = (
                                supabase
                                .table("portfolio_valuations")
                                .select("*")
                                .eq(
                                    "portfolio_id",
                                    selected_portfolio_id
                                )
                                .order(
                                    "valuation_date",
                                    desc=True
                                )
                                .execute()
                            )

                            if not rows.data:

                                st.info(
                                    "Geen valuations gevonden"
                                )

                            else:

                                valuations_df = pd.DataFrame(
                                    rows.data
                                )

                                valuations_df[
                                    "Verwijderen"
                                ] = False

                                edited_df = st.data_editor(
                                    valuations_df,
                                    use_container_width=True,
                                    hide_index=True,
                                    disabled=[
                                        col
                                        for col in valuations_df.columns
                                        if col != "Verwijderen"
                                    ]
                                )

                                delete_ids = (
                                    edited_df[
                                        edited_df["Verwijderen"]
                                    ]["id"]
                                    .tolist()
                                )

                                st.info(
                                    f"{len(delete_ids)} valuation(s) geselecteerd"
                                )

                                confirm_delete = st.checkbox(
                                    "Ik weet zeker dat ik deze valuations wil verwijderen",
                                    key="confirm_delete_valuations"
                                )

                                if (
                                    len(delete_ids) > 0
                                    and confirm_delete
                                ):

                                    if st.button(
                                        "Verwijder geselecteerde valuations",
                                        type="primary",
                                        key="delete_valuations_button"
                                    ):

                                        deleted = 0

                                        for valuation_id in delete_ids:

                                            try:

                                                # Eerst valuation_positions verwijderen

                                                (
                                                    supabase
                                                    .table(
                                                        "valuation_positions"
                                                    )
                                                    .delete()
                                                    .eq(
                                                        "valuation_id",
                                                        valuation_id
                                                    )
                                                    .execute()
                                                )

                                                # Daarna valuation verwijderen

                                                (
                                                    supabase
                                                    .table(
                                                        "portfolio_valuations"
                                                    )
                                                    .delete()
                                                    .eq(
                                                        "id",
                                                        valuation_id
                                                    )
                                                    .execute()
                                                )

                                                deleted += 1

                                            except Exception as e:

                                                st.error(
                                                    f"Fout bij valuation {valuation_id}: {e}"
                                                )

                                        st.success(
                                            f"{deleted} valuation(s) verwijderd"
                                        )

                                        st.rerun()


                        # ==========================
                        # Valuation Positions
                        # ==========================

                        with tab5:

                            valuations = (
                                supabase
                                .table("portfolio_valuations")
                                .select("id")
                                .eq(
                                    "portfolio_id",
                                    selected_portfolio_id
                                )
                                .execute()
                            )

                            valuation_ids = [
                                row["id"]
                                for row in valuations.data
                            ]

                            if not valuation_ids:

                                st.info(
                                    "Geen valuations gevonden"
                                )

                            else:

                                rows = (
                                    supabase
                                    .table("valuation_positions")
                                    .select("*")
                                    .in_(
                                        "valuation_id",
                                        valuation_ids
                                    )
                                    .execute()
                                )

                                if not rows.data:

                                    st.info(
                                        "Geen valuation positions gevonden"
                                    )

                                else:

                                    positions_df = pd.DataFrame(
                                        rows.data
                                    )

                                    positions_df[
                                        "Verwijderen"
                                    ] = False

                                    edited_df = st.data_editor(
                                        positions_df,
                                        use_container_width=True,
                                        hide_index=True,
                                        disabled=[
                                            col
                                            for col in positions_df.columns
                                            if col != "Verwijderen"
                                        ]
                                    )

                                    delete_ids = (
                                        edited_df[
                                            edited_df["Verwijderen"]
                                        ]["id"]
                                        .tolist()
                                    )

                                    st.info(
                                        f"{len(delete_ids)} positie(s) geselecteerd"
                                    )

                                    confirm_delete = st.checkbox(
                                        "Ik weet zeker dat ik deze valuation positions wil verwijderen",
                                        key="confirm_delete_valuation_positions"
                                    )

                                    if (
                                        len(delete_ids) > 0
                                        and confirm_delete
                                    ):

                                        if st.button(
                                            "Verwijder geselecteerde valuation positions",
                                            type="primary",
                                            key="delete_valuation_positions_button"
                                        ):

                                            deleted = 0

                                            for position_id in delete_ids:

                                                try:

                                                    (
                                                        supabase
                                                        .table(
                                                            "valuation_positions"
                                                        )
                                                        .delete()
                                                        .eq(
                                                            "id",
                                                            position_id
                                                        )
                                                        .execute()
                                                    )

                                                    deleted += 1

                                                except Exception as e:

                                                    st.error(
                                                        f"Fout bij positie {position_id}: {e}"
                                                    )

                                            st.success(
                                                f"{deleted} valuation position(s) verwijderd"
                                            )

                                            st.rerun()

                            # ==========================
                            # Year Baselines
                            # ==========================

                            with tab6:

                                rows = (
                                    supabase
                                    .table("year_baselines")
                                    .select("*")
                                    .eq(
                                        "portfolio_id",
                                        selected_portfolio_id
                                    )
                                    .order(
                                        "year",
                                        desc=True
                                    )
                                    .execute()
                                )

                                if not rows.data:

                                    st.info(
                                        "Geen year baselines gevonden"
                                    )

                                else:

                                    baselines_df = pd.DataFrame(
                                        rows.data
                                    )

                                    baselines_df[
                                        "Verwijderen"
                                    ] = False

                                    edited_df = st.data_editor(
                                        baselines_df,
                                        use_container_width=True,
                                        hide_index=True,
                                        disabled=[
                                            col
                                            for col in baselines_df.columns
                                            if col != "Verwijderen"
                                        ]
                                    )

                                    delete_ids = (
                                        edited_df[
                                            edited_df["Verwijderen"]
                                        ]["id"]
                                        .tolist()
                                    )

                                    if delete_ids:

                                        st.warning(
                                            f"{len(delete_ids)} baseline(s) geselecteerd"
                                        )

                                    confirm_delete = st.checkbox(
                                        "Ik weet zeker dat ik deze year baselines wil verwijderen",
                                        key="confirm_delete_year_baselines"
                                    )

                                    if (
                                        len(delete_ids) > 0
                                        and confirm_delete
                                    ):

                                        if st.button(
                                            "Verwijder geselecteerde year baselines",
                                            type="primary",
                                            key="delete_year_baselines_button"
                                        ):

                                            deleted = 0

                                            for baseline_id in delete_ids:

                                                try:

                                                    (
                                                        supabase
                                                        .table(
                                                            "year_baselines"
                                                        )
                                                        .delete()
                                                        .eq(
                                                            "id",
                                                            baseline_id
                                                        )
                                                        .execute()
                                                    )

                                                    deleted += 1

                                                except Exception as e:

                                                    st.error(
                                                        f"Fout bij baseline {baseline_id}: {e}"
                                                    )

                                            st.success(
                                                f"{deleted} year baseline(s) verwijderd"
                                            )

                                            st.rerun()

                    except Exception as e:

                        st.error(e)
                    
# =====================
# Analyse
# =====================

if tab10 is not None:

    with tab10:

        if not st.session_state.get(
            "logged_in",
            False
        ):

            st.warning(
                "Log eerst in."
            )

        else:

            if not st.session_state.get(
                "portfolio_id"
            ):

                st.info(
                    "Selecteer eerst een portefeuille in 'Mijn Portefeuille'."
                )

            else:
                
                st.subheader(
                    "Dashboard"
                )

                try:

                    valuations = (
                        supabase
                        .table(
                            "portfolio_valuations"
                        )
                        .select("*")
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .order(
                            "valuation_date"
                        )
                        .execute()
                    )

                    snapshots = (
                        supabase
                        .table(
                            "monthly_snapshots"
                        )
                        .select("*")
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .eq(
                            "is_active",
                            True
                        )
                        .execute()
                    )

                    baseline = (
                        supabase
                        .table(
                            "year_baselines"
                        )
                        .select("*")
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .order(
                            "year",
                            desc=True
                        )
                        .limit(1)
                        .execute()
                    )

                    if valuations.data:

                        current_value = (
                            valuations
                            .data[-1]
                            ["total_value"]
                        )

                        start_value = (
                            baseline.data[0]["start_value"]
                            if baseline.data
                            else 0
                        )

                        total_personal = sum(
                            s["personal_contribution"]
                            or 0
                            for s in snapshots.data
                        )

                        total_employer = sum(
                            s["employer_contribution"]
                            or 0
                            for s in snapshots.data
                        )

                        total_bonus = sum(
                            s["bonus_total"]
                            or 0
                            for s in snapshots.data
                        )

                        total_cost = sum(
                            s["costs_total"]
                            or 0
                            for s in snapshots.data
                        )

                        result = (
                            current_value
                            - start_value
                            - total_personal
                            - total_employer
                            - total_bonus
                            + total_cost
                        )

                        col1,col2,col3,col4 = (
                            st.columns(4)
                        )

                        with col1:
                            st.metric(
                                "Waarde",
                                f"€{current_value:,.0f}"
                            )

                        with col2:
                            st.metric(
                                "Begin jaar",
                                f"€{start_value:,.0f}"
                            )

                        with col3:
                            st.metric(
                                "Inleg",
                                f"€{total_personal + total_employer:,.0f}"
                            )

                        with col4:
                            st.metric(
                                "Resultaat",
                                f"€{result:,.0f}"
                            )

                except Exception as e:

                    st.error(e)

    #blok 2
                st.divider()

                col1, col2 = st.columns([1, 2])

                with col1:

                    st.subheader(
                        "Vermogensontwikkeling"
                    )

                    try:

                        if valuations.data:

                            trend_df = pd.DataFrame(
                                valuations.data
                            )

                            trend_df[
                                "valuation_date"
                            ] = pd.to_datetime(
                                trend_df[
                                    "valuation_date"
                                ]
                            )

                            st.line_chart(
                                trend_df.set_index(
                                    "valuation_date"
                                )[
                                    "total_value"
                                ]
                            )

                    except Exception as e:

                        st.error(e)

                with col2:

                    st.subheader(
                        "Fondstrends"
                    )

                    try:

                        valuations_funds = (
                            supabase
                            .table(
                                "portfolio_valuations"
                            )
                            .select(
                                "id,valuation_date"
                            )
                            .eq(
                                "portfolio_id",
                                st.session_state.portfolio_id
                            )
                            .order(
                                "valuation_date"
                            )
                            .execute()
                        )

                        valuation_df = pd.DataFrame(
                            valuations_funds.data
                        )

                        valuation_df[
                            "valuation_date"
                        ] = pd.to_datetime(
                            valuation_df[
                                "valuation_date"
                            ]
                        )

                        positions = (
                            supabase
                            .table(
                                "valuation_positions"
                            )
                            .select("*")
                            .execute()
                        )

                        pos_df = pd.DataFrame(
                            positions.data
                        )

                        funds = (
                            supabase
                            .table(
                                "funds"
                            )
                            .select(
                                "id,current_name"
                            )
                            .execute()
                        )

                        funds_df = pd.DataFrame(
                            funds.data
                        )

                        merged = (
                            pos_df
                            .merge(
                                valuation_df,
                                left_on="valuation_id",
                                right_on="id"
                            )
                            .merge(
                                funds_df,
                                left_on="fund_id",
                                right_on="id"
                            )
                        )

                        chart_df = (
                            merged
                            .pivot_table(
                                index="valuation_date",
                                columns="current_name",
                                values="value"
                            )
                            .sort_index()
                        )

                        st.line_chart(
                            chart_df
                        )

                    except Exception as e:

                        st.error(e)
    #blok 3
                st.divider()

                st.subheader(
                    "Cashflow"
                )

                try:

                    if snapshots.data:

                        cash_df = pd.DataFrame(
                            snapshots.data
                        )

                        cash_df[
                            "snapshot_date"
                        ] = pd.to_datetime(
                            cash_df[
                                "snapshot_date"
                            ]
                        )

                        cash_df = (
                            cash_df.sort_values(
                                "snapshot_date"
                            )
                        )

                        st.dataframe(
                            cash_df[
                                [
                                    "snapshot_date",
                                    "personal_contribution",
                                    "employer_contribution",
                                    "bonus_total",
                                    "costs_total"
                                ]
                            ],
                            use_container_width=True
                        )

                except Exception as e:

                    st.error(e)
                
                st.divider()

                st.subheader(
                    "Fondsallocatie"
                )

                try:

                    latest = (
                        supabase
                        .table(
                            "portfolio_valuations"
                        )
                        .select(
                            "id"
                        )
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .order(
                            "valuation_date",
                            desc=True
                        )
                        .limit(1)
                        .execute()
                    )

                    if latest.data:

                        valuation_id = (
                            latest.data[0]["id"]
                        )

                        positions = (
                            supabase
                            .table(
                                "valuation_positions"
                            )
                            .select(
                                "*"
                            )
                            .eq(
                                "valuation_id",
                                valuation_id
                            )
                            .execute()
                        )

                        if positions.data:

                            alloc_df = pd.DataFrame(
                                positions.data
                            )

                            funds = (
                                supabase
                                .table(
                                    "funds"
                                )
                                .select(
                                    "id,current_name"
                                )
                                .execute()
                            )

                            funds_df = pd.DataFrame(
                                funds.data
                            )

                            alloc_df = alloc_df.merge(
                                funds_df,
                                left_on="fund_id",
                                right_on="id",
                                how="left"
                            )

                            total = (
                                alloc_df[
                                    "value"
                                ]
                                .sum()
                            )

                            alloc_df[
                                "weight_pct"
                            ] = (
                                alloc_df[
                                    "value"
                                ]
                                / total
                                * 100
                            )

                            alloc_df = (
                                alloc_df[
                                    [
                                        "current_name",
                                        "value",
                                        "weight_pct"
                                    ]
                                ]
                                .rename(
                                    columns={
                                        "current_name":
                                            "Fonds",

                                        "value":
                                            "Waarde",

                                        "weight_pct":
                                            "Gewicht %"
                                    }
                                )
                                .sort_values(
                                    "Waarde",
                                    ascending=False
                                )
                            )

                            st.dataframe(
                                alloc_df,
                                use_container_width=True
                            )

                except Exception as e:

                    st.error(e)

                
                st.divider()

                st.subheader(
                    "Performance Matrix"
                )

                try:

                    valuations = (
                        supabase
                        .table(
                            "portfolio_valuations"
                        )
                        .select(
                            "id,valuation_date,total_value,price_date,total_value"
                        )
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .order(
                            "price_date"
                        )
                        .execute()
                    )

                    positions = (
                        supabase
                        .table(
                            "valuation_positions"
                        )
                        .select(
                            "valuation_id,fund_id,value,price_date"
                        )
                        .eq(
                            "is_active",
                            True
                        )
                        .execute()
                    )

                    funds = (
                        supabase
                        .table(
                            "funds"
                        )
                        .select(
                            "id,current_name"
                        )
                        .execute()
                    )

                    valuation_df = pd.DataFrame(
                        valuations.data
                    )

                    pos_df = pd.DataFrame(
                        positions.data
                    )

                    funds_df = pd.DataFrame(
                        funds.data
                    )

                    valuation_df[
                        "price_date"
                    ] = pd.to_datetime(
                        valuation_df[
                            "price_date"
                        ]
                    )

                    merged = (
                        pos_df
                        .merge(
                            valuation_df,
                            left_on="valuation_id",
                            right_on="id"
                        )
                        .merge(
                            funds_df,
                            left_on="fund_id",
                            right_on="id"
                        )
                    )

                    merged[
                        "valuation_date"
                    ] = pd.to_datetime(
                        merged[
                            "valuation_date"
                        ]
                    )
                    #st.write(
                    #    merged.columns.tolist()
                    #)
                    merged["price_date_x"] = pd.to_datetime(
                        merged["price_date_x"]
                    )

                    matrix_df = pd.DataFrame()

                    matrix_df[
                        "Datum"
                    ] = sorted(
                        merged[
                            "price_date_x"
                        ].unique()
                    )

                    #st.write(
                    #    sorted(
                    #        merged[
                    #            "current_name"
                    #        ].unique()
                    #    )
                    #)
                    for fund_name in sorted(
                        merged[
                            "current_name"
                        ].unique()
                    ):

                        fund_history = (
                            merged[
                                merged[
                                    "current_name"
                                ]
                                == fund_name
                            ]
                            .sort_values(
                                "price_date_x"
                            )
                        )

                        values = (
                            fund_history
                            .drop_duplicates(
                                subset=["price_date_x"],
                                keep="last"
                            )
                            .set_index(
                                "price_date_x"
                            )[
                                "value"
                            ]
                        )

                        values = values.reindex(
                            matrix_df[
                                "Datum"
                            ]
                        )

                        short_name = (
                            fund_name
                            .replace(
                                "Zwitserleven ",
                                ""
                            )
                        )
                        initials = "".join(
                            word[0].upper()
                            for word in short_name.split()
                        )

                        delta_eur_name = (
                            f"{initials} Δ€"
                        )

                        delta_pct_name = (
                            f"{initials} Δ%"
                        )

                        matrix_df[
                            f"{short_name}"
                        ] = (
                            pd.Series(values.values)
                            .round(2)
                        )

                        matrix_df[
                            delta_eur_name
                        ] = (
                            matrix_df[
                                short_name
                            ]
                            .diff()
                            .round(2)
                        )

                        matrix_df[
                            delta_pct_name
                        ] = (
                            matrix_df[
                                short_name
                            ]
                            .pct_change()
                            .mul(100)
                            .round(2)
                        )

                    totals = (
                        valuation_df
                        .sort_values(
                            "valuation_date"
                        )
                        .drop_duplicates(
                            subset=["price_date"],
                            keep="last"
                        )
                    )

                    totals["price_date"] = pd.to_datetime(
                        totals["price_date"]
                    )

                    totals = (
                        totals
                        .set_index(
                            "price_date"
                        )[
                            "total_value"
                        ]
                    )

                    totals = totals.reindex(
                        pd.to_datetime(
                            matrix_df["Datum"]
                        )
                    )

                    matrix_df[
                        "Totaal"
                    ] = totals.values

                    matrix_df[
                        "Totaal Δ€"
                    ] = (
                        matrix_df[
                            "Totaal"
                        ]
                        .diff()
                        .round(2)
                    )

                    matrix_df[
                        "Totaal Δ%"
                    ] = (
                        matrix_df[
                            "Totaal"
                        ]
                        .pct_change()
                        .mul(100)
                        .round(2)
                    )

                    matrix_df[
                        "Datum"
                    ] = matrix_df[
                        "Datum"
                    ].dt.date

                    def color_delta(val):

                        if pd.isna(val):
                            return ""

                        if val > 0:
                            return "color: lightgreen"

                        if val < 0:
                            return "color: salmon"

                        return ""
                    delta_columns = [
                        col
                        for col in matrix_df.columns
                        if "Δ€" in col
                        or "Δ%" in col
                    ]

                    matrix_df = matrix_df.round(2)

                    styled_df = (
                        matrix_df
                        .style
                        .format(precision=2)
                        .map(
                            color_delta,
                            subset=delta_columns
                        )
                    )

                    st.dataframe(
                        styled_df,
                        use_container_width=True,
                        height=600
                    )
                
                except Exception as e:

                    st.error(e)
    #############################
                st.divider()

                st.subheader(
                    "Resultaat sinds eerste waardering"
                )

                try:

                    summary_rows = []

                    fund_columns = [
                        col
                        for col in matrix_df.columns
                        if (
                            col != "Datum"
                            and "Δ" not in col
                            and col != "Totaal"
                        )
                    ]

                    for fund in fund_columns:

                        start_value = (
                            matrix_df[fund]
                            .dropna()
                            .iloc[0]
                        )

                        current_value = (
                            matrix_df[fund]
                            .dropna()
                            .iloc[-1]
                        )

                        profit = (
                            current_value
                            - start_value
                        )

                        return_pct = (
                            (
                                current_value
                                / start_value
                            )
                            - 1
                        ) * 100

                        summary_rows.append({
                            "Fonds": fund,
                            "Startwaarde": start_value,
                            "Huidige waarde": current_value,
                            "Verschil €": profit,
                            "Rendement %": return_pct
                        })

                    summary_df = pd.DataFrame(
                        summary_rows
                    )
                    baseline = (
                        supabase
                        .table(
                            "year_baselines"
                        )
                        .select(
                            "start_value"
                        )
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .eq(
                            "year",
                            datetime.now().year
                        )
                        .execute()
                    )
                    baseline_value = (
                        baseline.data[0]["start_value"]
                        if baseline.data
                        else summary_df["Startwaarde"].sum()
                    )
                    total_row = pd.DataFrame([
                        {
                            "Fonds": "TOTAAL",

                            "Startwaarde":
                                baseline_value,

                            "Huidige waarde":
                                summary_df[
                                    "Huidige waarde"
                                ].sum(),

                            "Verschil €":
                                (
                                    summary_df[
                                        "Huidige waarde"
                                    ].sum()
                                    - baseline_value
                                ),

                            "Rendement %":
                                (
                                    (
                                        summary_df[
                                            "Huidige waarde"
                                        ].sum()
                                        /
                                        baseline_value
                                    )
                                    - 1
                                )
                                * 100
                        }
                    ])

                    summary_df = (
                        summary_df
                        .sort_values(
                            "Rendement %",
                            ascending=False
                        )
                    )
                    summary_df = pd.concat(
                        [
                            summary_df,
                            total_row
                        ],
                        ignore_index=True
                    )
                    summary_df = (
                        summary_df
                        .sort_values(
                            "Rendement %",
                            ascending=False
                        )
                    )

                    def color_summary(val):

                        if val > 0:
                            return "color: lightgreen"

                        if val < 0:
                            return "color: salmon"

                        return ""

                    styled_summary = (
                        summary_df
                        .style
                        .format(
                            precision=2
                        )
                        .map(
                            color_summary,
                            subset=[
                                "Verschil €",
                                "Rendement %"
                            ]
                        )
                    )

                    st.dataframe(
                        styled_summary,
                        use_container_width=True
                    )

                except Exception as e:

                    st.error(e)

                st.divider()

                st.subheader(
                    "Portfolio Prognose"
                )

                try:

                    valuations = (
                        supabase
                        .table(
                            "portfolio_valuations"
                        )
                        .select("*")
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .order(
                            "valuation_date"
                        )
                        .execute()
                    )

                    snapshots = (
                        supabase
                        .table(
                            "monthly_snapshots"
                        )
                        .select("*")
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .eq(
                            "is_active",
                            True
                        )
                        .order(
                            "snapshot_date",
                            desc=True
                        )
                        .limit(1)
                        .execute()
                    )

                    if valuations.data and snapshots.data:

                        valuation_df = pd.DataFrame(
                            valuations.data
                        )

                        current_value = float(
                            valuation_df[
                                "total_value"
                            ].iloc[-1]
                        )

                        latest_snapshot = (
                            snapshots.data[0]
                        )

                        annual_contribution = (
                            (
                                float(
                                    latest_snapshot.get(
                                        "personal_contribution",
                                        0
                                    )
                                )
                                +
                                float(
                                    latest_snapshot.get(
                                        "employer_contribution",
                                        0
                                    )
                                )
                                +
                                float(
                                    latest_snapshot.get(
                                        "bonus_total",
                                        0
                                    )
                                )
                                -
                                float(
                                    latest_snapshot.get(
                                        "costs_total",
                                        0
                                    )
                                )
                            )
                            * 12
                        )

                        years = st.slider(
                            "Jaren vooruit",
                            1,
                            40,
                            20
                        )

                        col1, col2, col3 = st.columns(3)

                        with col1:

                            worst_rate = (
                                st.number_input(
                                    "Worst Case (%)",
                                    value=3.0,
                                    step=0.5
                                )
                                / 100
                            )

                        with col2:

                            base_rate = (
                                st.number_input(
                                    "Base Case (%)",
                                    value=7.0,
                                    step=0.5
                                )
                                / 100
                            )

                        with col3:

                            best_rate = (
                                st.number_input(
                                    "Best Case (%)",
                                    value=10.0,
                                    step=0.5
                                )
                                / 100
                            )

                        scenarios = {
                            "Worst Case":
                                worst_rate,
                            "Base Case":
                                base_rate,
                            "Best Case":
                                best_rate
                        }

                        current_year = (
                            datetime.now()
                            .year
                        )

                        rows = []

                        for (
                            scenario,
                            rate
                        ) in scenarios.items():

                            value = (
                                current_value
                            )

                            for year in range(
                                years + 1
                            ):

                                rows.append(
                                    {
                                        "Jaar":
                                            current_year
                                            + year,

                                        "Waarde":
                                            value,

                                        "Scenario":
                                            scenario
                                    }
                                )

                                value = (
                                    value
                                    * (
                                        1 + rate
                                    )
                                ) + (
                                    annual_contribution
                                )

                        projection_df = (
                            pd.DataFrame(
                                rows
                            )
                        )

                        fig = px.line(
                            projection_df,
                            x="Jaar",
                            y="Waarde",
                            color="Scenario",
                            markers=True
                        )

                        fig.update_layout(
                            title=(
                                "Verwachte "
                                "Portefeuillewaarde"
                            ),
                            xaxis_title="Jaar",
                            yaxis_title="Waarde (€)",
                            hovermode="x unified",
                            height=600
                        )

                        st.plotly_chart(
                            fig,
                            use_container_width=True
                        )

                        final_values = (
                            projection_df
                            .groupby(
                                "Scenario"
                            )
                            ["Waarde"]
                            .last()
                        )

                        c1, c2, c3 = (
                            st.columns(3)
                        )
                        with c1:

                            st.metric(
                                "Worst Case",
                                f"€ {final_values['Worst Case']:,.2f}"
                                .replace(",", "X")
                                .replace(".", ",")
                                .replace("X", ".")
                            )

                        with c2:

                            st.metric(
                                "Base Case",
                                f"€ {final_values['Base Case']:,.2f}"
                                .replace(",", "X")
                                .replace(".", ",")
                                .replace("X", ".")
                            )

                        with c3:

                            st.metric(
                                "Best Case",
                                f"€ {final_values['Best Case']:,.2f}"
                                .replace(",", "X")
                                .replace(".", ",")
                                .replace("X", ".")
                            )

                except Exception as e:

                    st.error(e)


    ####################################           
                st.divider()

                st.subheader(
                    "Datakwaliteit"
                )

                try:

                    col1,col2,col3 = (
                        st.columns(3)
                    )

                    with col1:

                        st.metric(
                            "Snapshots",
                            len(
                                snapshots.data
                            )
                        )

                    with col2:

                        st.metric(
                            "Waarderingen",
                            len(
                                valuations.data
                            )
                        )

                    with col3:

                        if valuations.data:

                            st.metric(
                                "Laatste waardering",
                                valuations.data[-1][
                                    "valuation_date"
                                ]
                            )

                except Exception as e:

                    st.error(e)
        
# =====================
# Test page
# =====================

if tab11 is not None:

    with tab11:

        if not st.session_state.get(
            "logged_in",
            False
        ):

            st.warning(
                "Log eerst in."
            )

        else:

            if not st.session_state.get(
                "portfolio_id"
            ):

                st.info(
                    "Selecteer eerst een portefeuille in 'Mijn Portefeuille'."
                )

            else:
                
                st.subheader(
                    "Dashboard"
                )

                try:

                    valuations = (
                        supabase
                        .table(
                            "portfolio_valuations"
                        )
                        .select("*")
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .order(
                            "valuation_date"
                        )
                        .execute()
                    )

                    snapshots = (
                        supabase
                        .table(
                            "monthly_snapshots"
                        )
                        .select("*")
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .eq(
                            "is_active",
                            True
                        )
                        .execute()
                    )

                    baseline = (
                        supabase
                        .table(
                            "year_baselines"
                        )
                        .select("*")
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .order(
                            "year",
                            desc=True
                        )
                        .limit(1)
                        .execute()
                    )

                    if valuations.data:

                        current_value = (
                            valuations
                            .data[-1]
                            ["total_value"]
                        )

                        start_value = (
                            baseline.data[0]["start_value"]
                            if baseline.data
                            else 0
                        )

                        total_personal = sum(
                            s["personal_contribution"]
                            or 0
                            for s in snapshots.data
                        )

                        total_employer = sum(
                            s["employer_contribution"]
                            or 0
                            for s in snapshots.data
                        )

                        total_bonus = sum(
                            s["bonus_total"]
                            or 0
                            for s in snapshots.data
                        )

                        total_cost = sum(
                            s["costs_total"]
                            or 0
                            for s in snapshots.data
                        )

                        result = (
                            current_value
                            - start_value
                            - total_personal
                            - total_employer
                            - total_bonus
                            + total_cost
                        )

                        col1,col2,col3,col4 = (
                            st.columns(4)
                        )

                        with col1:
                            st.metric(
                                "Waarde",
                                f"€{current_value:,.0f}"
                            )

                        with col2:
                            st.metric(
                                "Begin jaar",
                                f"€{start_value:,.0f}"
                            )

                        with col3:
                            st.metric(
                                "Inleg",
                                f"€{total_personal + total_employer:,.0f}"
                            )

                        with col4:
                            st.metric(
                                "Resultaat",
                                f"€{result:,.0f}"
                            )

                except Exception as e:

                    st.error(e)

    #blok 2
                st.divider()

                col1, col2 = st.columns([1, 2])

                with col1:

                    st.subheader(
                        "Vermogensontwikkeling"
                    )

                    try:

                        if valuations.data:

                            trend_df = pd.DataFrame(
                                valuations.data
                            )

                            trend_df[
                                "valuation_date"
                            ] = pd.to_datetime(
                                trend_df[
                                    "valuation_date"
                                ]
                            )

                            st.line_chart(
                                trend_df.set_index(
                                    "valuation_date"
                                )[
                                    "total_value"
                                ]
                            )

                    except Exception as e:

                        st.error(e)

                with col2:

                    st.subheader(
                        "Fondstrends"
                    )

                    try:

                        valuations_funds = (
                            supabase
                            .table(
                                "portfolio_valuations"
                            )
                            .select(
                                "id,valuation_date"
                            )
                            .eq(
                                "portfolio_id",
                                st.session_state.portfolio_id
                            )
                            .order(
                                "valuation_date"
                            )
                            .execute()
                        )

                        valuation_df = pd.DataFrame(
                            valuations_funds.data
                        )

                        valuation_df[
                            "valuation_date"
                        ] = pd.to_datetime(
                            valuation_df[
                                "valuation_date"
                            ]
                        )

                        positions = (
                            supabase
                            .table(
                                "valuation_positions"
                            )
                            .select("*")
                            .execute()
                        )

                        pos_df = pd.DataFrame(
                            positions.data
                        )

                        funds = (
                            supabase
                            .table(
                                "funds"
                            )
                            .select(
                                "id,current_name"
                            )
                            .execute()
                        )

                        funds_df = pd.DataFrame(
                            funds.data
                        )

                        merged = (
                            pos_df
                            .merge(
                                valuation_df,
                                left_on="valuation_id",
                                right_on="id"
                            )
                            .merge(
                                funds_df,
                                left_on="fund_id",
                                right_on="id"
                            )
                        )

                        chart_df = (
                            merged
                            .pivot_table(
                                index="valuation_date",
                                columns="current_name",
                                values="value"
                            )
                            .sort_index()
                        )

                        st.line_chart(
                            chart_df
                        )

                    except Exception as e:

                        st.error(e)
    #blok 3
                st.divider()

                st.subheader(
                    "Cashflow"
                )

                try:

                    if snapshots.data:

                        cash_df = pd.DataFrame(
                            snapshots.data
                        )

                        cash_df[
                            "snapshot_date"
                        ] = pd.to_datetime(
                            cash_df[
                                "snapshot_date"
                            ]
                        )

                        cash_df = (
                            cash_df.sort_values(
                                "snapshot_date"
                            )
                        )

                        st.dataframe(
                            cash_df[
                                [
                                    "snapshot_date",
                                    "personal_contribution",
                                    "employer_contribution",
                                    "bonus_total",
                                    "costs_total"
                                ]
                            ],
                            use_container_width=True
                        )

                except Exception as e:

                    st.error(e)
                
                st.divider()

                st.subheader(
                    "Fondsallocatie"
                )

                try:

                    latest = (
                        supabase
                        .table(
                            "portfolio_valuations"
                        )
                        .select(
                            "id"
                        )
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .order(
                            "valuation_date",
                            desc=True
                        )
                        .limit(1)
                        .execute()
                    )

                    if latest.data:

                        valuation_id = (
                            latest.data[0]["id"]
                        )

                        positions = (
                            supabase
                            .table(
                                "valuation_positions"
                            )
                            .select(
                                "*"
                            )
                            .eq(
                                "valuation_id",
                                valuation_id
                            )
                            .execute()
                        )

                        if positions.data:

                            alloc_df = pd.DataFrame(
                                positions.data
                            )

                            funds = (
                                supabase
                                .table(
                                    "funds"
                                )
                                .select(
                                    "id,current_name"
                                )
                                .execute()
                            )

                            funds_df = pd.DataFrame(
                                funds.data
                            )

                            alloc_df = alloc_df.merge(
                                funds_df,
                                left_on="fund_id",
                                right_on="id",
                                how="left"
                            )

                            total = (
                                alloc_df[
                                    "value"
                                ]
                                .sum()
                            )

                            alloc_df[
                                "weight_pct"
                            ] = (
                                alloc_df[
                                    "value"
                                ]
                                / total
                                * 100
                            )

                            alloc_df = (
                                alloc_df[
                                    [
                                        "current_name",
                                        "value",
                                        "weight_pct"
                                    ]
                                ]
                                .rename(
                                    columns={
                                        "current_name":
                                            "Fonds",

                                        "value":
                                            "Waarde",

                                        "weight_pct":
                                            "Gewicht %"
                                    }
                                )
                                .sort_values(
                                    "Waarde",
                                    ascending=False
                                )
                            )

                            st.dataframe(
                                alloc_df,
                                use_container_width=True
                            )

                except Exception as e:

                    st.error(e)

                
                st.divider()

                st.subheader(
                    "Performance Matrix"
                )

                try:

                    valuations = (
                        supabase
                        .table(
                            "portfolio_valuations"
                        )
                        .select(
                            "id,valuation_date,total_value,price_date,total_value"
                        )
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .order(
                            "price_date"
                        )
                        .execute()
                    )

                    positions = (
                        supabase
                        .table(
                            "valuation_positions"
                        )
                        .select(
                            "valuation_id,fund_id,value,price_date"
                        )
                        .eq(
                            "is_active",
                            True
                        )
                        .execute()
                    )

                    funds = (
                        supabase
                        .table(
                            "funds"
                        )
                        .select(
                            "id,current_name"
                        )
                        .execute()
                    )

                    valuation_df = pd.DataFrame(
                        valuations.data
                    )

                    pos_df = pd.DataFrame(
                        positions.data
                    )

                    funds_df = pd.DataFrame(
                        funds.data
                    )

                    valuation_df[
                        "price_date"
                    ] = pd.to_datetime(
                        valuation_df[
                            "price_date"
                        ]
                    )

                    merged = (
                        pos_df
                        .merge(
                            valuation_df,
                            left_on="valuation_id",
                            right_on="id"
                        )
                        .merge(
                            funds_df,
                            left_on="fund_id",
                            right_on="id"
                        )
                    )

                    merged[
                        "valuation_date"
                    ] = pd.to_datetime(
                        merged[
                            "valuation_date"
                        ]
                    )
                    #st.write(
                    #    merged.columns.tolist()
                    #)
                    merged["price_date_x"] = pd.to_datetime(
                        merged["price_date_x"]
                    )

                    matrix_df = pd.DataFrame()

                    matrix_df[
                        "Datum"
                    ] = sorted(
                        merged[
                            "price_date_x"
                        ].unique()
                    )

                    #st.write(
                    #    sorted(
                    #        merged[
                    #            "current_name"
                    #        ].unique()
                    #    )
                    #)
                    for fund_name in sorted(
                        merged[
                            "current_name"
                        ].unique()
                    ):

                        fund_history = (
                            merged[
                                merged[
                                    "current_name"
                                ]
                                == fund_name
                            ]
                            .sort_values(
                                "price_date_x"
                            )
                        )

                        values = (
                            fund_history
                            .drop_duplicates(
                                subset=["price_date_x"],
                                keep="last"
                            )
                            .set_index(
                                "price_date_x"
                            )[
                                "value"
                            ]
                        )

                        values = values.reindex(
                            matrix_df[
                                "Datum"
                            ]
                        )

                        short_name = (
                            fund_name
                            .replace(
                                "Zwitserleven ",
                                ""
                            )
                        )
                        initials = "".join(
                            word[0].upper()
                            for word in short_name.split()
                        )

                        delta_eur_name = (
                            f"{initials} Δ€"
                        )

                        delta_pct_name = (
                            f"{initials} Δ%"
                        )

                        matrix_df[
                            f"{short_name}"
                        ] = (
                            pd.Series(values.values)
                            .round(2)
                        )

                        matrix_df[
                            delta_eur_name
                        ] = (
                            matrix_df[
                                short_name
                            ]
                            .diff()
                            .round(2)
                        )

                        matrix_df[
                            delta_pct_name
                        ] = (
                            matrix_df[
                                short_name
                            ]
                            .pct_change()
                            .mul(100)
                            .round(2)
                        )

                    totals = (
                        valuation_df
                        .sort_values(
                            "valuation_date"
                        )
                        .drop_duplicates(
                            subset=["price_date"],
                            keep="last"
                        )
                    )

                    totals["price_date"] = pd.to_datetime(
                        totals["price_date"]
                    )

                    totals = (
                        totals
                        .set_index(
                            "price_date"
                        )[
                            "total_value"
                        ]
                    )

                    totals = totals.reindex(
                        pd.to_datetime(
                            matrix_df["Datum"]
                        )
                    )

                    matrix_df[
                        "Totaal"
                    ] = totals.values

                    matrix_df[
                        "Totaal Δ€"
                    ] = (
                        matrix_df[
                            "Totaal"
                        ]
                        .diff()
                        .round(2)
                    )

                    matrix_df[
                        "Totaal Δ%"
                    ] = (
                        matrix_df[
                            "Totaal"
                        ]
                        .pct_change()
                        .mul(100)
                        .round(2)
                    )

                    matrix_df[
                        "Datum"
                    ] = matrix_df[
                        "Datum"
                    ].dt.date

                    def color_delta(val):

                        if pd.isna(val):
                            return ""

                        if val > 0:
                            return "color: lightgreen"

                        if val < 0:
                            return "color: salmon"

                        return ""
                    delta_columns = [
                        col
                        for col in matrix_df.columns
                        if "Δ€" in col
                        or "Δ%" in col
                    ]

                    matrix_df = matrix_df.round(2)

                    styled_df = (
                        matrix_df
                        .style
                        .format(precision=2)
                        .map(
                            color_delta,
                            subset=delta_columns
                        )
                    )

                    st.dataframe(
                        styled_df,
                        use_container_width=True,
                        height=600
                    )
                
                except Exception as e:

                    st.error(e)
    #############################
                st.divider()

                st.subheader(
                    "Resultaat sinds eerste waardering"
                )

                try:

                    summary_rows = []

                    fund_columns = [
                        col
                        for col in matrix_df.columns
                        if (
                            col != "Datum"
                            and "Δ" not in col
                            and col != "Totaal"
                        )
                    ]

                    for fund in fund_columns:

                        start_value = (
                            matrix_df[fund]
                            .dropna()
                            .iloc[0]
                        )

                        current_value = (
                            matrix_df[fund]
                            .dropna()
                            .iloc[-1]
                        )

                        profit = (
                            current_value
                            - start_value
                        )

                        return_pct = (
                            (
                                current_value
                                / start_value
                            )
                            - 1
                        ) * 100

                        summary_rows.append({
                            "Fonds": fund,
                            "Startwaarde": start_value,
                            "Huidige waarde": current_value,
                            "Verschil €": profit,
                            "Rendement %": return_pct
                        })

                    summary_df = pd.DataFrame(
                        summary_rows
                    )
                    baseline = (
                        supabase
                        .table(
                            "year_baselines"
                        )
                        .select(
                            "start_value"
                        )
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .eq(
                            "year",
                            datetime.now().year
                        )
                        .execute()
                    )
                    baseline_value = (
                        baseline.data[0]["start_value"]
                        if baseline.data
                        else summary_df["Startwaarde"].sum()
                    )
                    total_row = pd.DataFrame([
                        {
                            "Fonds": "TOTAAL",

                            "Startwaarde":
                                baseline_value,

                            "Huidige waarde":
                                summary_df[
                                    "Huidige waarde"
                                ].sum(),

                            "Verschil €":
                                (
                                    summary_df[
                                        "Huidige waarde"
                                    ].sum()
                                    - baseline_value
                                ),

                            "Rendement %":
                                (
                                    (
                                        summary_df[
                                            "Huidige waarde"
                                        ].sum()
                                        /
                                        baseline_value
                                    )
                                    - 1
                                )
                                * 100
                        }
                    ])

                    summary_df = (
                        summary_df
                        .sort_values(
                            "Rendement %",
                            ascending=False
                        )
                    )
                    summary_df = pd.concat(
                        [
                            summary_df,
                            total_row
                        ],
                        ignore_index=True
                    )
                    summary_df = (
                        summary_df
                        .sort_values(
                            "Rendement %",
                            ascending=False
                        )
                    )

                    def color_summary(val):

                        if val > 0:
                            return "color: lightgreen"

                        if val < 0:
                            return "color: salmon"

                        return ""

                    styled_summary = (
                        summary_df
                        .style
                        .format(
                            precision=2
                        )
                        .map(
                            color_summary,
                            subset=[
                                "Verschil €",
                                "Rendement %"
                            ]
                        )
                    )

                    st.dataframe(
                        styled_summary,
                        use_container_width=True
                    )

                except Exception as e:

                    st.error(e)

                st.divider()

                st.subheader(
                    "Portfolio Prognose"
                )

                try:

                    valuations = (
                        supabase
                        .table(
                            "portfolio_valuations"
                        )
                        .select("*")
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .order(
                            "valuation_date"
                        )
                        .execute()
                    )

                    snapshots = (
                        supabase
                        .table(
                            "monthly_snapshots"
                        )
                        .select("*")
                        .eq(
                            "portfolio_id",
                            st.session_state.portfolio_id
                        )
                        .eq(
                            "is_active",
                            True
                        )
                        .order(
                            "snapshot_date",
                            desc=True
                        )
                        .limit(1)
                        .execute()
                    )

                    if valuations.data and snapshots.data:

                        valuation_df = pd.DataFrame(
                            valuations.data
                        )

                        current_value = float(
                            valuation_df[
                                "total_value"
                            ].iloc[-1]
                        )

                        latest_snapshot = (
                            snapshots.data[0]
                        )

                        annual_contribution = (
                            (
                                float(
                                    latest_snapshot.get(
                                        "personal_contribution",
                                        0
                                    )
                                )
                                +
                                float(
                                    latest_snapshot.get(
                                        "employer_contribution",
                                        0
                                    )
                                )
                                +
                                float(
                                    latest_snapshot.get(
                                        "bonus_total",
                                        0
                                    )
                                )
                                -
                                float(
                                    latest_snapshot.get(
                                        "costs_total",
                                        0
                                    )
                                )
                            )
                            * 12
                        )

                        years = st.slider(
                            "Jaren vooruit",
                            min_value=1,
                            max_value=40,
                            value=20,
                            key="test_portfolio_prognose_years"
                        )

                        first_total = (
                            matrix_df["Totaal"]
                            .dropna()
                            .iloc[0]
                        )

                        last_total = (
                            matrix_df["Totaal"]
                            .dropna()
                            .iloc[-1]
                        )
                        historical_return = (
                            (
                                last_total
                                / first_total
                            )
                            - 1
                        ) * 100

                        show_historical = st.checkbox(
                            f"Toon historisch rendement "
                            f"({historical_return:.2f}%)",
                            value=True,
                            key="show_historical_return"
                        )

                        col1, col2, col3 = st.columns(3)

                        with col1:

                            worst_rate = (
                                st.number_input(
                                    "Worst Case (%)",
                                    value=3.0,
                                    step=0.5,
                                    key="test_worst_case_worst"
                                )
                                / 100
                            )

                        with col2:

                            base_rate = (
                                st.number_input(
                                    "Base Case (%)",
                                    value=7.0,
                                    step=0.5,
                                    key="test_worst_case_base"
                                )
                                / 100
                            )

                        with col3:

                            best_rate = (
                                st.number_input(
                                    "Best Case (%)",
                                    value=10.0,
                                    step=0.5,
                                    key="test_worst_case_best"
                                )
                                / 100
                            )

                        scenarios = {
                            "Worst Case": worst_rate,
                            "Base Case": base_rate,
                            "Best Case": best_rate
                        }


                        if show_historical:

                            scenarios[
                                f"Historisch ({historical_return:.2f}%)"
                            ] = (
                                historical_return
                                / 100
                            )

                        current_year = (
                            datetime.now()
                            .year
                        )

                        rows = []

                        for (
                            scenario,
                            rate
                        ) in scenarios.items():

                            value = (
                                current_value
                            )

                            for year in range(
                                years + 1
                            ):

                                rows.append(
                                    {
                                        "Jaar":
                                            current_year
                                            + year,

                                        "Waarde":
                                            value,

                                        "Scenario":
                                            scenario
                                    }
                                )

                                value = (
                                    value
                                    * (
                                        1 + rate
                                    )
                                ) + (
                                    annual_contribution
                                )

                        projection_df = (
                            pd.DataFrame(
                                rows
                            )
                        )

                        fig = px.line(
                            projection_df,
                            x="Jaar",
                            y="Waarde",
                            color="Scenario",
                            markers=True
                        )

                        fig.update_layout(
                            title=(
                                "Verwachte "
                                "Portefeuillewaarde"
                            ),
                            xaxis_title="Jaar",
                            yaxis_title="Waarde (€)",
                            hovermode="x unified",
                            height=600
                        )

                        st.plotly_chart(
                            fig,
                            use_container_width=True,
                            key="test_portfolio_prognose_chart"
                        )

                        final_values = (
                            projection_df
                            .groupby(
                                "Scenario"
                            )
                            ["Waarde"]
                            .last()
                        )

                        c1, c2, c3 = (
                            st.columns(3)
                        )
                        with c1:

                            st.metric(
                                "Worst Case",
                                f"€ {final_values['Worst Case']:,.2f}"
                                .replace(",", "X")
                                .replace(".", ",")
                                .replace("X", ".")
                            )

                        with c2:

                            st.metric(
                                "Base Case",
                                f"€ {final_values['Base Case']:,.2f}"
                                .replace(",", "X")
                                .replace(".", ",")
                                .replace("X", ".")
                            )

                        with c3:

                            st.metric(
                                "Best Case",
                                f"€ {final_values['Best Case']:,.2f}"
                                .replace(",", "X")
                                .replace(".", ",")
                                .replace("X", ".")
                            )

                except Exception as e:

                    st.error(e)


    ####################################           
                st.divider()

                st.subheader(
                    "Datakwaliteit"
                )

                try:

                    col1,col2,col3 = (
                        st.columns(3)
                    )

                    with col1:

                        st.metric(
                            "Snapshots",
                            len(
                                snapshots.data
                            )
                        )

                    with col2:

                        st.metric(
                            "Waarderingen",
                            len(
                                valuations.data
                            )
                        )

                    with col3:

                        if valuations.data:

                            st.metric(
                                "Laatste waardering",
                                valuations.data[-1][
                                    "valuation_date"
                                ]
                            )

                except Exception as e:

                    st.error(e)

# ==========================
# RLS Debug
# ==========================
if tab12 is not None:
    with tab12:

        if not st.session_state.get("logged_in"):

            st.warning(
                "Log in om deze pagina te gebruiken."
            )

        else:

            st.success(
                f"Ingelogd als "
                f"{st.session_state.username}"
            )

            st.header("🔐 RLS Debug")

            st.divider()

            st.subheader("Session State")

            st.write(
                {
                    "logged_in":
                        st.session_state.get(
                            "logged_in"
                        ),

                    "user_id":
                        st.session_state.get(
                            "user_id"
                        ),

                    "username":
                        st.session_state.get(
                            "username"
                        ),

                    "role":
                        st.session_state.get(
                            "role"
                        ),

                    "portfolio_id":
                        st.session_state.get(
                            "portfolio_id"
                        ),

                    "portfolio_name":
                        st.session_state.get(
                            "portfolio_name"
                        )
                }
            )

            st.divider()

            st.subheader("Auth Session")

            try:

                session = (
                    supabase
                    .auth
                    .get_session()
                )

                st.write(session)

            except Exception as e:

                st.error(
                    f"Session Error: {e}"
                )

            st.divider()

            st.subheader("Auth User")

            try:

                user = (
                    supabase
                    .auth
                    .get_user()
                )

                st.write(user)

            except Exception as e:

                st.error(
                    f"User Error: {e}"
                )

            st.divider()

            st.subheader("Profiles Test")

            try:

                profiles = (
                    supabase
                    .table("profiles")
                    .select("*")
                    .execute()
                )

                st.success(
                    f"{len(profiles.data)} profiel(en)"
                )

                st.dataframe(
                    pd.DataFrame(
                        profiles.data
                    ),
                    use_container_width=True,
                    height=250
                )

            except Exception as e:

                st.error(
                    f"Profiles Error: {e}"
                )

            st.divider()

            st.subheader("Portfolios Test")

            try:

                portfolios = (
                    supabase
                    .table("portfolios")
                    .select("*")
                    .execute()
                )

                st.success(
                    f"{len(portfolios.data)} portfolio(s)"
                )

                st.dataframe(
                    pd.DataFrame(
                        portfolios.data
                    ),
                    use_container_width=True,
                    height=250
                )

            except Exception as e:

                st.error(
                    f"Portfolios Error: {e}"
                )

            st.divider()

            st.subheader("Profile Mapping Test")

            try:

                if (
                    st.session_state.get(
                        "user_id"
                    )
                ):

                    profile = (
                        supabase
                        .table("profiles")
                        .select("*")
                        .eq(
                            "id",
                            st.session_state.user_id
                        )
                        .single()
                        .execute()
                    )

                    st.success(
                        "Profile gevonden"
                    )

                    st.write(
                        profile.data
                    )

                else:

                    st.warning(
                        "Geen user_id aanwezig in session"
                    )

            except Exception as e:

                st.error(
                    f"Mapping Error: {e}"
                )

            st.divider()

            st.subheader("JWT Controle")

            try:

                session = (
                    supabase
                    .auth
                    .get_session()
                )

                if (
                    session
                    and
                    session.session
                ):

                    st.success(
                        "JWT aanwezig"
                    )

                    st.write(
                        {
                            "access_token_present":
                                bool(
                                    session.session.access_token
                                ),

                            "refresh_token_present":
                                bool(
                                    session.session.refresh_token
                                ),

                            "expires_at":
                                session.session.expires_at
                        }
                    )

                else:

                    st.warning(
                        "Geen actieve session gevonden"
                    )

            except Exception as e:

                st.error(
                    f"JWT Error: {e}"
                )

            st.divider()

            st.subheader("RLS Smoke Test")

            if st.button(
                "🧪 Test Profiles"
            ):

                try:

                    result = (
                        supabase
                        .table("profiles")
                        .select("*")
                        .execute()
                    )

                    st.success(
                        f"{len(result.data)} record(s)"
                    )

                    st.dataframe(
                        pd.DataFrame(
                            result.data
                        ),
                        use_container_width=True
                    )

                except Exception as e:

                    st.error(e)

            if st.button(
                "🧪 Test Portfolios"
            ):

                try:

                    result = (
                        supabase
                        .table("portfolios")
                        .select("*")
                        .execute()
                    )

                    st.success(
                        f"{len(result.data)} record(s)"
                    )

                    st.dataframe(
                        pd.DataFrame(
                            result.data
                        ),
                        use_container_width=True
                    )

                except Exception as e:

                    st.error(e)     

            st.subheader("Auth Login Test")

            try:

                result = supabase.auth.get_user()

                st.write(result)

            except Exception as e:

                st.error(e)     

            st.subheader("Session Object")

            try:

                session = supabase.auth.get_session()

                st.write(type(session))
                st.write(session)

            except Exception as e:

                st.error(e)

            st.subheader("Login Result Test")

            if st.button("Toon huidige auth status"):

                try:

                    result = supabase.auth.get_session()

                    st.write(result)

                except Exception as e:

                    st.error(e)
            
            st.subheader("Portfolio's")

            try:

                portfolios = (
                    supabase
                    .table("portfolios")
                    .select("*")
                    .execute()
                )

                st.write(
                    f"{len(portfolios.data)} portfolio(s)"
                )

                st.dataframe(
                    pd.DataFrame(
                        portfolios.data
                    )
                )

            except Exception as e:

                st.error(e)