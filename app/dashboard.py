with tab1:
    st.subheader("Overview")

    # =========================
    # CONTEXT
    # =========================
    start_date = pivot.index.min().strftime("%d-%m-%Y")
    end_date = pivot.index.max().strftime("%d-%m-%Y")
    days = (pivot.index.max() - pivot.index.min()).days

    st.caption(
        f"Periode: {start_date} → {end_date} ({days} dagen).\n"
        "Rendement = groei over periode.\n"
        "Volatiliteit = risico (schommelingen).\n"
        "Sharpe = rendement per risico."
    )

    # =========================
    # METRICS
    # =========================
    if len(pivot) > 1:
        ret = (pivot.iloc[-1] / pivot.iloc[0] - 1) * 100

        best = ret.idxmax()
        worst = ret.idxmin()

        vol = returns.std() * np.sqrt(TRADING_DAYS)
        sharpe = (returns.mean()*TRADING_DAYS)/vol.replace(0,np.nan)

        def short(x):
            return x if len(x) < 18 else x[:18] + "..."

        c1,c2,c3,c4,c5 = st.columns(5)

        c1.metric("Gem. rendement", f"{ret.mean():.2f}%")

        c2.metric("Beste fonds", short(best))
        c2.caption(best)

        c3.metric("Slechtste fonds", short(worst))
        c3.caption(worst)

        c4.metric("Gem. volatiliteit", f"{vol.mean():.2f}")
        c5.metric("Gem. Sharpe", f"{sharpe.mean():.2f}")

    st.markdown("---")

    # =========================
    # TREND 1 (MET BENCHMARK + HIGHLIGHT)
    # =========================
    st.subheader("Prijsontwikkeling")

    fig = go.Figure()

    # benchmark = gemiddelde
    benchmark = pivot.mean(axis=1)

    for col in pivot.columns:
        width = 4 if col == best else 2

        fig.add_trace(go.Scatter(
            x=pivot.index,
            y=pivot[col],
            name=col,
            line=dict(width=width)
        ))

    # benchmark lijn
    fig.add_trace(go.Scatter(
        x=pivot.index,
        y=benchmark,
        name="Benchmark (gemiddelde)",
        line=dict(dash="dash", width=3)
    ))

    fig.update_layout(
        hovermode="x unified",
        xaxis_title="Datum",
        yaxis_title="Prijs"
    )

    st.plotly_chart(fig, use_container_width=True)

    # =========================
    # TREND 2 (GENORMALISEERD)
    # =========================
    st.subheader("Genormaliseerde groei")

    norm = pivot / pivot.iloc[0] * 100
    bench_norm = norm.mean(axis=1)

    fig2 = go.Figure()

    for col in norm.columns:
        width = 4 if col == best else 2

        fig2.add_trace(go.Scatter(
            x=norm.index,
            y=norm[col],
            name=col,
            line=dict(width=width)
        ))

    fig2.add_trace(go.Scatter(
        x=norm.index,
        y=bench_norm,
        name="Benchmark",
        line=dict(dash="dash", width=3)
    ))

    fig2.update_layout(
        hovermode="x unified",
        xaxis_title="Datum",
        yaxis_title="Index (start = 100)"
    )

    st.plotly_chart(fig2, use_container_width=True)

    # =========================
    # DRAWDOWN
    # =========================
    st.subheader("Drawdown (verlies vanaf piek)")

    drawdown = pivot / pivot.cummax() - 1

    fig3 = go.Figure()

    for col in drawdown.columns:
        fig3.add_trace(go.Scatter(
            x=drawdown.index,
            y=drawdown[col]*100,
            name=col
        ))

    fig3.update_layout(
        hovermode="x unified",
        xaxis_title="Datum",
        yaxis_title="Drawdown (%)"
    )

    st.plotly_chart(fig3, use_container_width=True)

    # =========================
    # RANKING TABLE
    # =========================
    st.subheader("Ranking")

    ranking = pd.DataFrame({
        "Rendement %": ret,
        "Volatiliteit": vol,
        "Sharpe": sharpe
    })

    ranking = ranking.sort_values("Sharpe", ascending=False)

    st.dataframe(ranking, use_container_width=True)