import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import get_connection
from datetime import date

st.set_page_config(layout="wide")
st.title("Revenue & EBITDA Forecast Tracker")

# ---------- Submit Forecast Form ----------
st.subheader("Submit Forecast")
region = st.selectbox("Region", ["USA", "Canada", "Europe", "India", "Australia", "Africa"])
week = st.date_input("Week", value=date.today())
flash_est = st.number_input("Flash Estimate", min_value=0.0, step=1000.0)
actuals = st.number_input("Actuals", min_value=0.0, step=1000.0)

def calculate_metrics(flash, actuals, week):
    fva = flash - actuals
    acc_pct = fva / actuals if actuals != 0 else None
    acc_score = max(0, 1 - abs(fva) / abs(actuals)) if actuals != 0 else 0
    month = week.month
    eom_flag = ""
    return fva, acc_pct, acc_score, month, eom_flag

if st.button("Submit"):
    fva, acc_pct, acc_score, month, eom_flag = calculate_metrics(flash_est, actuals, week)
    insert_query = text('''
        INSERT INTO revenue_forecast (
            region, week, flash_est, actuals,
            flash_vs_act, pct_variance, accuracy, month, eom
        ) VALUES (:region, :week, :flash_est, :actuals, :fva, :acc_pct, :acc_score, :month, :eom_flag)
    ''')
    with get_connection() as conn:
        conn.execute(insert_query, {
            'region': region,
            'week': week,
            'flash_est': flash_est,
            'actuals': actuals,
            'fva': fva,
            'acc_pct': acc_pct,
            'acc_score': acc_score,
            'month': month,
            'eom_flag': eom_flag
        })
        conn.commit()
    st.success("Forecast submitted.")

# ---------- Load and Display Table ----------
with get_connection() as conn:
    df = pd.read_sql("SELECT * FROM revenue_forecast", conn)

df['week'] = pd.to_datetime(df['week'])
df['flash_vs_act'] = df['flash_est'] - df['actuals']
df['pct_variance'] = df['flash_vs_act'] / df['actuals']
df['accuracy'] = (1 - abs(df['flash_vs_act']) / abs(df['actuals'])).clip(lower=0)
df['month'] = df['week'].dt.month

df.rename(columns={
    'week': 'Week',
    'region': 'Region',
    'flash_est': 'Flash Est',
    'actuals': 'Actuals',
    'flash_vs_act': 'Flash vs Act',
    'pct_variance': '% Variance',
    'accuracy': 'Accuracy',
    'month': 'Month',
    'eom': 'EOM'
}, inplace=True)

st.subheader("Forecast Table")
st.dataframe(df, use_container_width=True)

# ---------- Export ----------
st.download_button(
    label="Export to CSV",
    data=df.to_csv(index=False).encode('utf-8'),
    file_name='revenue_forecast.csv',
    mime='text/csv'
)