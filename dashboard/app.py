import altair as alt
import pandas as pd
import psycopg
import streamlit as st

from src.quality.volume_check import THRESHOLD
from src.storage.runs import get_connection


st.set_page_config(page_title="ForecastGuard", page_icon="🛡️", layout="wide")


# ---------- Colors and styles ----------

INK = "#1d2733"
MUTED = "#5b6776"
LINE = "#e3e7ec"
SURFACE = "#f6f8fa"
GREEN = "#1f7a4d"
RED = "#b3261e"

st.markdown(
    f"""
    <style>
    .block-container {{ padding-top: 2.5rem; max-width: 1150px; }}

    .fg-header {{ display: flex; justify-content: space-between;
                  align-items: flex-end; border-bottom: 1px solid {LINE};
                  padding-bottom: 0.9rem; margin-bottom: 1.6rem; }}
    .fg-title {{ font-size: 2.1rem; font-weight: 700; color: {INK};
                 line-height: 1.1; }}
    .fg-subtitle {{ color: {MUTED}; font-size: 1rem; margin-top: 0.3rem; }}
    .fg-last-run {{ color: {MUTED}; font-size: 0.9rem; text-align: right; }}

    .fg-status {{ border-radius: 10px; padding: 1.4rem 1.6rem;
                  margin-bottom: 2rem; color: white; }}
    .fg-status-label {{ font-size: 0.95rem; opacity: 0.85; }}
    .fg-status-title {{ font-size: 2rem; font-weight: 700; margin: 0.2rem 0; }}
    .fg-status-detail {{ font-size: 1.05rem; opacity: 0.95; }}

    .fg-section {{ font-size: 1.25rem; font-weight: 700; color: {INK};
                   margin: 2.2rem 0 0.9rem 0; }}

    .fg-tile {{ background: {SURFACE}; border: 1px solid {LINE};
                border-radius: 8px; padding: 1rem 1.1rem; min-height: 150px; }}
    .fg-tile-label {{ color: {MUTED}; font-size: 0.9rem; }}
    .fg-tile-value {{ color: {INK}; font-size: 1.9rem; font-weight: 700;
                      font-variant-numeric: tabular-nums; margin: 0.15rem 0; }}
    .fg-tile-note {{ color: {MUTED}; font-size: 0.85rem; }}

    .fg-bar {{ position: relative; height: 8px; background: {LINE};
               border-radius: 4px; margin: 0.55rem 0 0.4rem 0; }}
    .fg-bar-fill {{ height: 100%; border-radius: 4px; }}
    .fg-bar-mark {{ position: absolute; top: -4px; width: 2px; height: 16px;
                    background: {INK}; }}
    [data-testid="stMarkdownContainer"] h3 {{ font-size: 1.15rem; }}
    [data-testid="stMarkdownContainer"] h4 {{ font-size: 1rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Data loading ----------

def run_query(query):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [column.name for column in cursor.description]
            rows = cursor.fetchall()

    return pd.DataFrame(rows, columns=columns)


@st.cache_data(ttl=30)
def load_runs():
    query = """
        SELECT
            id,
            executed_at,
            data_date,
            current_orders,
            historical_average_7d,
            volume_ratio,
            status,
            forecast_date,
            predicted_orders,
            diagnosis
        FROM forecast_runs
        ORDER BY executed_at DESC;
    """

    try:
        runs = run_query(query)
    except psycopg.errors.UndefinedTable:
        return pd.DataFrame()

    for column in ["historical_average_7d", "volume_ratio"]:
        runs[column] = runs[column].astype(float)

    return runs


@st.cache_data(ttl=30)
def load_daily_sales():
    query = """
        SELECT
            order_date,
            number_of_orders
        FROM analytics.fct_daily_sales
        ORDER BY order_date;
    """

    daily_sales = run_query(query)
    daily_sales["order_date"] = pd.to_datetime(daily_sales["order_date"])

    # Same rule as the volume check: average of the 7 previous days.
    baseline = daily_sales["number_of_orders"].shift(1).rolling(7).mean()
    daily_sales["threshold"] = baseline * THRESHOLD
    daily_sales["below_threshold"] = (
        daily_sales["number_of_orders"] < daily_sales["threshold"]
    )

    return daily_sales


# ---------- Building blocks ----------

def section_title(text):
    st.markdown(f'<div class="fg-section">{text}</div>', unsafe_allow_html=True)


def tile(label, value, note="", extra_html=""):
    # Built on one line: blank lines or indentation would be read as Markdown.
    return (
        '<div class="fg-tile">'
        f'<div class="fg-tile-label">{label}</div>'
        f'<div class="fg-tile-value">{value}</div>'
        f"{extra_html}"
        f'<div class="fg-tile-note">{note}</div>'
        "</div>"
    )


def show_tiles(tiles):
    columns = st.columns(len(tiles))

    for column, html in zip(columns, tiles):
        column.markdown(html, unsafe_allow_html=True)


# ---------- Page sections ----------

def render_header(latest_run):
    last_run = latest_run["executed_at"].strftime("%Y-%m-%d %H:%M")

    st.markdown(
        f"""
        <div class="fg-header">
            <div>
                <div class="fg-title">ForecastGuard</div>
                <div class="fg-subtitle">Sales forecast reliability monitor</div>
            </div>
            <div class="fg-last-run">Last pipeline run<br>{last_run}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status(latest_run):
    if latest_run["status"] == "PUBLISHED":
        color = GREEN
        title = f"{int(latest_run['predicted_orders']):,} orders expected"
        detail = (
            f"Forecast for {latest_run['forecast_date']} published. "
            f"Data from {latest_run['data_date']} passed the volume check."
        )
        label = "Forecast published"
    else:
        color = RED
        title = "No forecast today"
        detail = (
            f"Orders on {latest_run['data_date']} reached only "
            f"{latest_run['volume_ratio']:.0%} of the usual volume. "
            f"Publishing requires at least {THRESHOLD:.0%}."
        )
        label = "Forecast blocked"

    st.markdown(
        f"""
        <div class="fg-status" style="background: {color};">
            <div class="fg-status-label">{label}</div>
            <div class="fg-status-title">{title}</div>
            <div class="fg-status-detail">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_quality_indicators(latest_run):
    section_title("Data quality check")

    ratio = latest_run["volume_ratio"]
    passed = ratio >= THRESHOLD
    ratio_color = GREEN if passed else RED
    difference = latest_run["current_orders"] - latest_run["historical_average_7d"]

    ratio_bar = (
        '<div class="fg-bar">'
        f'<div class="fg-bar-fill" style="width: {min(ratio, 1) * 100:.0f}%; '
        f'background: {ratio_color};"></div>'
        f'<div class="fg-bar-mark" style="left: {THRESHOLD * 100:.0f}%;"></div>'
        "</div>"
    )

    if latest_run["status"] == "PUBLISHED":
        forecast_value = f"{int(latest_run['predicted_orders']):,}"
        forecast_note = f"Orders expected on {latest_run['forecast_date']}"
    else:
        forecast_value = "Blocked"
        forecast_note = "Not published until data is reliable"

    show_tiles([
        tile(
            "Orders received",
            f"{latest_run['current_orders']:,}",
            f"On {latest_run['data_date']}",
        ),
        tile(
            "Usual daily volume",
            f"{latest_run['historical_average_7d']:,.0f}",
            f"Average of the 7 previous days ({difference:+,.0f} today)",
        ),
        tile(
            "Volume ratio",
            f'<span style="color: {ratio_color};">{ratio:.0%}</span>',
            f"Minimum required: {THRESHOLD:.0%}",
            ratio_bar,
        ),
        tile("Forecast", forecast_value, forecast_note),
    ])


def render_chart(daily_sales):
    section_title("Daily order volume")

    base = alt.Chart(daily_sales).encode(
        x=alt.X("order_date:T", title=None),
    )

    orders_line = base.mark_line(color=INK, strokeWidth=2).encode(
        y=alt.Y("number_of_orders:Q", title="Orders"),
        tooltip=[
            alt.Tooltip("order_date:T", title="Date"),
            alt.Tooltip("number_of_orders:Q", title="Orders"),
        ],
    )

    threshold_line = base.mark_line(
        color="#9aa5b1",
        strokeDash=[6, 4],
    ).encode(
        y="threshold:Q",
    )

    anomalies = base.transform_filter(
        alt.datum.below_threshold
    ).mark_point(
        color=RED,
        size=140,
        filled=True,
    ).encode(
        y="number_of_orders:Q",
    )

    st.altair_chart(
        (orders_line + threshold_line + anomalies).properties(height=320),
        width="stretch",
    )
    st.caption(
        f"Dashed line: minimum volume required ({THRESHOLD:.0%} of the previous "
        "7-day average). Red points are days below it."
    )


def render_diagnosis(latest_run):
    section_title("Incident diagnosis")

    if latest_run["diagnosis"]:
        st.caption(
            "Generated by Gemini from the pipeline figures. "
            "Hypotheses to verify, not conclusions."
        )
        with st.container(border=True):
            st.markdown(latest_run["diagnosis"])
    else:
        st.warning(
            "The AI diagnosis was unavailable for this run. "
            "The figures above remain valid."
        )


def render_history(runs):
    section_title("Run history")

    published = int((runs["status"] == "PUBLISHED").sum())
    blocked = int((runs["status"] == "BLOCKED").sum())

    show_tiles([
        tile("Runs recorded", f"{len(runs):,}", "Since the table was created"),
        tile("Forecasts published", f"{published:,}", "Data passed the check"),
        tile("Forecasts blocked", f"{blocked:,}", "Anomaly detected"),
    ])

    st.write("")

    history = runs[
        [
            "executed_at",
            "data_date",
            "current_orders",
            "volume_ratio",
            "status",
            "predicted_orders",
        ]
    ].rename(
        columns={
            "executed_at": "Run at",
            "data_date": "Data date",
            "current_orders": "Orders",
            "volume_ratio": "Volume ratio",
            "status": "Decision",
            "predicted_orders": "Forecast",
        }
    )
    history["Decision"] = history["Decision"].map(
        {"PUBLISHED": "Published", "BLOCKED": "Blocked"}
    )
    history["Forecast"] = history["Forecast"].astype("Int64")

    styled_history = history.style.map(
        lambda value: f"color: {GREEN if value == 'Published' else RED}; "
                      "font-weight: 600;",
        subset=["Decision"],
    )

    st.dataframe(
        styled_history,
        hide_index=True,
        width="stretch",
        column_config={
            "Run at": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"),
            "Volume ratio": st.column_config.NumberColumn(format="percent"),
        },
    )


# ---------- Page ----------

try:
    runs = load_runs()
    daily_sales = load_daily_sales()
except psycopg.OperationalError:
    st.title("ForecastGuard")
    st.error(
        "Cannot connect to PostgreSQL. "
        "Check that the containers are running with `docker compose up -d`."
    )
    st.stop()

if runs.empty:
    st.title("ForecastGuard")
    st.info(
        "No run recorded yet. "
        "Trigger the forecastguard_pipeline DAG in Airflow, then refresh this page."
    )
    st.stop()

latest_run = runs.iloc[0]

render_header(latest_run)
render_status(latest_run)
render_quality_indicators(latest_run)
render_chart(daily_sales)

if latest_run["status"] == "BLOCKED":
    render_diagnosis(latest_run)

render_history(runs)