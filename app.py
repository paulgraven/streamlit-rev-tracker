import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import text
from database import get_engine

st.set_page_config(layout="wide")
st.title("Weekly Revenue & EBITDA Forecast")

engine = get_engine()

# ---------- Helpers ----------
def compute_metrics(flash_val: float, actual_val: float):
    fva = flash_val - actual_val
    pct_var = (fva / actual_val) if actual_val != 0 else None
    acc = max(0.0, 1.0 - abs(fva) / abs(actual_val)) if actual_val != 0 else 0.0
    return fva, pct_var, acc

def get_existing_columns():
    with engine.connect() as conn:
        cols = pd.read_sql(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'revenue_forecast'
            """),
            conn
        )["column_name"].str.lower().tolist()
    return set(cols)

# ---------- Data Entry ----------
st.subheader("Submit Forecast")
financials = st.selectbox("Financials", ["Revenue", "EBITDA"])
region = st.selectbox("Region", ["USA", "Canada", "Europe", "India", "Australia", "Africa"])
week = st.date_input("Week", value=date.today())
flash_est = st.number_input("Flash Estimate", min_value=0.0, step=1000.0, format="%.2f")
actuals = st.number_input("Actuals", min_value=0.0, step=1000.0, format="%.2f")

if st.button("Submit"):
    existing = get_existing_columns()
    # Required base columns we will insert (must exist in your table)
    required = ["financials", "region", "week", "flash_est", "actuals"]
    missing_required = [c for c in required if c not in existing]
    if missing_required:
        st.error(f"Your table 'revenue_forecast' is missing required column(s): {', '.join(missing_required)}")
        st.stop()

    fva, pct_var, acc = compute_metrics(flash_est, actuals)
    month_num = week.month
    eom_val = ""  # default

    # Optional computed columns - insert only if they exist in the table
    optional_values = {}
    if "flash_vs_act" in existing: optional_values["flash_vs_act"] = float(fva)
    if "pct_variance" in existing: optional_values["pct_variance"] = None if pct_var is None else float(pct_var)
    if "accuracy" in existing:     optional_values["accuracy"] = float(acc)
    if "month" in existing:        optional_values["month"] = month_num
    if "eom" in existing:          optional_values["eom"] = eom_val

    # Build dynamic INSERT
    cols = ["financials", "region", "week", "flash_est", "actuals"] + list(optional_values.keys())
    params = {
        "financials": financials,
        "region": region,
        "week": week,  # SQLAlchemy handles date -> date
        "flash_est": float(flash_est),
        "actuals": float(actuals),
        **optional_values
    }
    placeholders = ", ".join([f":{c}" for c in cols])
    col_list = ", ".join(cols)

    insert_sql = text(f"INSERT INTO revenue_forecast ({col_list}) VALUES ({placeholders})")
    with engine.begin() as conn:
        conn.execute(insert_sql, params)

        # Maintain EOM if the table supports it
        if "eom" in existing:
            # Clear all EOM for this region/month/year
            conn.execute(
                text("""
                    UPDATE revenue_forecast
                    SET eom = ''
                    WHERE region = :region
                      AND DATE_PART('month', week) = :m
                      AND DATE_PART('year',  week) = :y
                """),
                {"region": region, "m": month_num, "y": week.year}
            )
            # Mark the max week as EOM for that same region/month/year
            conn.execute(
                text("""
                    WITH mx AS (
                      SELECT MAX(week) AS w
                      FROM revenue_forecast
                      WHERE region = :region
                        AND DATE_PART('month', week) = :m
                        AND DATE_PART('year',  week) = :y
                    )
                    UPDATE revenue_forecast
                    SET eom = 'EOM'
                    WHERE region = :region
                      AND DATE_PART('month', week) = :m
                      AND DATE_PART('year',  week) = :y
                      AND week = (SELECT w FROM mx)
                """),
                {"region": region, "m": month_num, "y": week.year}
            )

    st.success("Forecast submitted.")

# ---------- Data View ----------
with engine.connect() as conn:
    # Select * to avoid column name mismatches; sort using actual column name present
    df = pd.read_sql_query(text("SELECT * FROM revenue_forecast"), conn)

# Normalize for display (compute if missing)
cols = {c.lower(): c for c in df.columns}
# Parse week
if "week" in cols:
    df[cols["week"]] = pd.to_datetime(df[cols["week"]])

# Ensure derived columns exist for display
def ensure_col(name, compute_fn):
    if name not in df.columns:
        df[name] = compute_fn()

# Compute derived fields if table doesn’t store them
if ("flash_vs_act" in cols) and ("flash_est" in cols) and ("actuals" in cols):
    # If present, we still recompute to be safe (or you can skip)
    df[cols["flash_vs_act"]] = df[cols["flash_est"]] - df[cols["actuals"]]
else:
    ensure_col("flash_vs_act", lambda: df[cols["flash_est"]] - df[cols["actuals"]]
               if ("flash_est" in cols and "actuals" in cols) else pd.NA)

if ("pct_variance" not in df.columns) and ("flash_est" in cols) and ("actuals" in cols):
    ensure_col("pct_variance", lambda: (df[cols["flash_est"]] - df[cols["actuals"]]) / df[cols["actuals"]])

if ("accuracy" not in df.columns) and ("flash_est" in cols) and ("actuals" in cols):
    ensure_col("accuracy", lambda: (1 - (df[cols["flash_est"]] - df[cols["actuals"]]).abs() / df[cols["actuals"]].abs()).clip(lower=0))

if ("month" not in df.columns) and ("week" in cols):
    ensure_col("month", lambda: df[cols["week"]].dt.month)

# If EOM not stored, compute a display-only EOM
if ("eom" not in df.columns) and ("week" in cols) and ("region" in cols):
    temp = df.copy()
    temp["_month"] = temp[cols["week"]].dt.month
    latest = temp.groupby([cols["region"], "_month"])[cols["week"]].transform("max")
    df["eom"] = (temp[cols["week"]] == latest).map({True: "EOM", False: ""})

# Reorder/rename for a nice view if names are snake_case
rename_map = {}
for snake, nice in [
    ("financials", "Financials"),
    ("region", "Region"),
    ("week", "Week"),
    ("flash_est", "Flash Est"),
    ("actuals", "Actuals"),
    ("flash_vs_act", "Flash vs Act"),
    ("pct_variance", "% Variance"),
    ("accuracy", "Accuracy"),
    ("month", "Month"),
    ("eom", "EOM"),
]:
    if snake in cols:
        rename_map[cols[snake]] = nice

df_display = df.rename(columns=rename_map)

preferred_order = [c for _, c in [
    ("Financials", "Financials"),
    ("Region", "Region"),
    ("Week", "Week"),
    ("Flash Est", "Flash Est"),
    ("Actuals", "Actuals"),
    ("Flash vs Act", "Flash vs Act"),
    ("% Variance", "% Variance"),
    ("Accuracy", "Accuracy"),
    ("Month", "Month"),
    ("EOM", "EOM"),
] if c in df_display.columns]

st.subheader("Forecast Table")
st.dataframe(df_display[preferred_order] if preferred_order else df_display, use_container_width=True)

st.download_button(
    "Export to CSV",
    (df_display[preferred_order] if preferred_order else df_display).to_csv(index=False).encode("utf-8"),
    file_name="revenue_forecast.csv",
    mime="text/csv"
)