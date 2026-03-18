import pandas as pd

def normalize(df):
    return df / df.iloc[0] * 100

def performance(df):
    return (df.iloc[-1] - 100).sort_values(ascending=False)

def volatility(df):
    return df.pct_change().std().sort_values(ascending=False)

def sharpe_ratio(df, risk_free=0):
    returns = df.pct_change().dropna()
    return (returns.mean() - risk_free) / returns.std()
