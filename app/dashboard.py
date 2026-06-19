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
tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8,tab9 = st.tabs([
    "Overview",
    "Performance",
    "Risk",
    "Heatmap",
    "Optimizer",
    "Rebalance",
    "Raw Data",
    "Admin",
    "Mijn Portefeuille"
])

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
    st.subheader("Monte Carlo")

    capital = st.number_input("Kapitaal", 100, 1000000, 10000)

    mean = returns.mean().mean()
    std = returns.std().mean()

    sims = 100
    days = 100

    paths = []
    for _ in range(sims):
        prices = [capital]
        for _ in range(days):
            prices.append(prices[-1]*(1+np.random.normal(mean,std)))
        paths.append(prices)

    fig = go.Figure()
    for p in paths[:20]:
        fig.add_trace(go.Scatter(y=p, showlegend=False))
    st.plotly_chart(fig)

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

# =============
# admin
# =============
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

        profiles = (
            supabase
            .table("profiles")
            .select("*")
            .order("display_name")
            .execute()
        )
        import pandas as pd

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
            "Gebruiker uitnodigen"
        )
        with st.form(
            "invite_user_form"
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
            st.write(
                "Admin client geladen"
            )

# ==================
# Mijn Portefeuille
# ==================

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

                    (
                        supabase
                        .table("portfolios")
                        .insert({
                            "user_id": "b13578bd-ec93-49a2-b24f-ac8dc1608d50",
                            "name": new_name,
                            "is_active": True
                        })
                        .execute()
                    )

                    st.success(
                        "Portfolio opgeslagen"
                    )

                    st.session_state.new_portfolio = False

                    st.rerun()

                except Exception as e:

                    st.error(e)

        # -------------------------
        # Portfolio geopend
        # -------------------------

        if st.session_state.portfolio_id:

            
            st.success(
                f"Geopende portefeuille: "
                f"{st.session_state.portfolio_name}"
            )


            
            st.divider()

            

            col1, col2, col3, col4 = st.columns(4)

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

