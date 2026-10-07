"""Streamlit dashboard, backed by SQLite. Run:  streamlit run app.py"""
import json
from pathlib import Path
import pandas as pd, plotly.express as px, plotly.graph_objects as go, streamlit as st

from src import db
from src.categorize import MODEL_PATH, METRICS_PATH, train_and_evaluate
from src.parse import load_statement
from src.pipeline import ingest, summaries
from src.anomaly import flag_anomalies

st.set_page_config(page_title="Where did my money go?", page_icon="₹", layout="wide")
INK, TEAL, SAFFRON, RED = "#1B2A41", "#1F6F78", "#D98A00", "#B23A48"
CAT_COLORS = ["#1F6F78", "#D98A00", "#6D597A", "#5B8E7D", "#B23A48", "#4A6FA5", "#A68A64", "#7A9E9F", "#8D6B94", "#C9A227", "#5C6B73", "#9AA5B1", "#3D5A80"]
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"], .stMarkdown, button, input { font-family: 'IBM Plex Sans', sans-serif; font-variant-numeric: tabular-nums; }
.block-container { padding-top: 2rem; max-width: 1250px; }
h1 { font-weight: 600; letter-spacing: -0.02em; margin-bottom: 0; }
.sub { color:#5C6B73; margin: 0 0 1.2rem 0; }
.kpi { background:#fff; border:1px solid #DCE1E6; border-radius:6px; padding:14px 18px; }
.kpi .v { font-size:1.9rem; font-weight:600; line-height:1.15; } .kpi .l { color:#5C6B73; font-size:.85rem; } .kpi .n { font-size:.8rem; color:#5C6B73; }
.flag { background:#fff; border-left:4px solid #D98A00; padding:8px 14px; margin:6px 0; border-radius:0 6px 6px 0; }
.stTabs [data-baseweb="tab"] { font-weight:500; }
code { font-size:.85rem; }
</style>""", unsafe_allow_html=True)

fmt = lambda x: f"₹{x:,.0f}"


@st.cache_resource(show_spinner=False)
def get_conn():
    return db.connect()


@st.cache_resource(show_spinner="First run: training the categoriser on sample data...")
def ensure_model():
    if not MODEL_PATH.exists():
        df = load_statement("data/sample_statement.csv")
        train_and_evaluate(df, pd.read_csv("data/ground_truth.csv").true_category)
    return True


ensure_model()
conn = get_conn()

with st.sidebar:
    st.header("Your statement")
    up = st.file_uploader("Upload bank/UPI statement CSV", type="csv")
    st.caption("Stored locally in **data/finance.db** on this machine only - never uploaded anywhere else.")
    st.divider()
    st.caption("Statements loaded so far")
    hist = db.list_statements(conn)
    st.dataframe(hist.rename(columns={"n_transactions": "rows"}), hide_index=True, width="stretch", height=140)
    scope = st.radio("Show", ["Latest upload", "All statements combined"], index=0)

try:
    if up is not None:
        statement_id, _ = ingest(up, up.name, conn)
    elif hist.empty:
        statement_id, _ = ingest("data/sample_statement.csv", "sample_statement.csv", conn)
    else:
        statement_id = int(hist.id.iloc[0])
except ValueError as e:
    st.error(f"Couldn't read that file. {e}"); st.stop()

if scope == "All statements combined":
    tx = pd.read_sql("SELECT * FROM transactions ORDER BY date", conn, parse_dates=["date"])
    tx["is_anomaly"] = tx["is_anomaly"].astype(bool)
else:
    tx = db.load_statement(conn, statement_id)

months = sorted(tx.month.unique())
with st.sidebar:
    lo, hi = st.select_slider("Months", options=months, value=(months[0], months[-1])) if len(months) > 1 else (months[0], months[0])
view = tx[(tx.month >= lo) & (tx.month <= hi)]
S = summaries(view); mon = S["monthly"]

st.title("Where did my money go?")
st.markdown(f"<p class='sub'>{len(view):,} transactions, {lo} to {hi}. Categorised by rules + a small ML model, checked for oddities, stored in a local database.</p>", unsafe_allow_html=True)
if mon.empty: st.warning("No salary/income found in this range, so the health score can't be computed."); st.stop()
cur = mon.iloc[-1]
c = st.columns(4)
for col, (l, v, n) in zip(c, [("Income (latest month)", fmt(cur.income), cur.month), ("Spent", fmt(cur.spend), f"{cur.spend / cur.income:.0%} of income"),
                              ("Saved or invested", f"{cur.savings_rate:.0%}", "target: 20% or more"), ("Health score", f"{cur.health_score:.0f} / 100", cur.grade)]):
    col.markdown(f"<div class='kpi'><div class='l'>{l}</div><div class='v'>{v}</div><div class='n'>{n}</div></div>", unsafe_allow_html=True)

t1, t2, t3, t4, t5, t6, t7 = st.tabs(["Spending", "Health score", "Unusual transactions", "Subscriptions & payees", "Review & fix", "SQL explorer", "Model accuracy"])

with t1:
    a, b = st.columns([3, 2])
    m = mon.melt("month", ["income", "spend"], var_name="", value_name="₹")
    a.plotly_chart(px.bar(m, x="month", y="₹", color="", barmode="group", color_discrete_map={"income": TEAL, "spend": SAFFRON}, title="Income vs spending").update_layout(height=340, margin=dict(t=50, b=10)), width="stretch")
    sel = b.selectbox("Category split for", sorted(view.month.unique())[::-1])
    cm = S["by_category"].query("month == @sel and category != 'Rent'")
    b.plotly_chart(px.pie(cm, names="category", values="amount", hole=.55, color_discrete_sequence=CAT_COLORS, title=f"Spend by category, {sel} (excl. rent)").update_layout(height=340, margin=dict(t=50, b=10)), width="stretch")
    st.plotly_chart(px.bar(S["by_category"], x="month", y="amount", color="category", color_discrete_sequence=CAT_COLORS, title="Category trend").update_layout(height=340, margin=dict(t=50, b=10)), width="stretch")

with t2:
    a, b = st.columns([1, 2])
    g = go.Figure(go.Indicator(mode="gauge+number", value=cur.health_score, title={"text": f"{cur.month}: {cur.grade}"},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": INK}, "steps": [{"range": [0, 45], "color": "#E9C4C9"}, {"range": [45, 65], "color": "#F1DFB5"}, {"range": [65, 80], "color": "#CFE3E0"}, {"range": [80, 100], "color": "#A9CFC8"}]}))
    a.plotly_chart(g.update_layout(height=300, margin=dict(t=60, b=10)), width="stretch")
    mx = {"savings": 35, "needs": 25, "wants": 20, "stability": 10, "anomalies": 10}
    comp = pd.DataFrame({"part": [f"{k} (max {v})" for k, v in mx.items()], "points": [cur[f"pts_{k}"] for k in mx]})
    b.plotly_chart(px.bar(comp, x="points", y="part", orientation="h", text="points", color_discrete_sequence=[TEAL], title=f"What made up the score, {cur.month}").update_layout(height=300, margin=dict(t=50, b=10), yaxis_title=None), width="stretch")
    st.plotly_chart(px.line(mon, x="month", y="health_score", markers=True, range_y=[0, 100], color_discrete_sequence=[INK], title="Score over time").update_layout(height=300, margin=dict(t=50, b=10)), width="stretch")
    with st.expander("How the score is calculated"):
        st.markdown("""**Savings (35)**: full marks if you save or invest 20% or more of income. **Needs (25)**: rent, bills, groceries, health, transport, education at or under 50% of income. **Wants (20)**: food delivery, shopping, entertainment, transfers at or under 30%. **Stability (10)**: spending close to your recent average. **Anomalies (10)**: minus 3 for each flagged transaction. The thresholds follow the popular 50/30/20 budgeting rule.""")

with t3:
    an = view[view.is_anomaly].sort_values("date", ascending=False)
    st.write(f"**{len(an)} flagged** out of {len(view):,} transactions. Each flag says why, so you can judge it.")
    for _, r in an.head(12).iterrows():
        st.markdown(f"<div class='flag'><b>{r.date:%d %b %Y}</b>  ·  {r.merchant}  ·  <b>{fmt(r.amount)}</b> ({r.category})<br><span style='color:#5C6B73'>{r.flag_reasons}</span></div>", unsafe_allow_html=True)
    st.dataframe(an[["date", "merchant", "category", "amount", "flag_reasons"]], hide_index=True, width="stretch")

with t4:
    a, b = st.columns(2)
    rc = S["recurring"]
    a.subheader("Recurring payments"); a.caption("Same payee, 3+ months, similar amount.")
    a.dataframe(rc.rename(columns={"avg": "monthly ₹", "yearly_cost": "yearly ₹"})[["merchant", "category", "months", "monthly ₹", "yearly ₹"]], hide_index=True, width="stretch")
    if len(rc): a.info(f"Recurring payments (excluding rent) cost about {fmt(rc.query('category != \"Rent\"').yearly_cost.sum())} a year.")
    b.subheader("Top payees")
    top = S["by_merchant"].head(12).rename(columns={"sum": "total ₹", "count": "payments"})
    b.plotly_chart(px.bar(top.iloc[::-1], x="total ₹", y="merchant", color="category", orientation="h", color_discrete_sequence=CAT_COLORS).update_layout(height=430, margin=dict(t=10, b=10)), width="stretch")

with t5:
    q = view[(view.category_source != "rule") & ((view.category_source == "needs review") | (view.confidence < .75))].sort_values("confidence")
    st.write(f"**{len(q)} transactions** the model wasn't sure about, least confident first. "
             f"Fix the category and apply - it's saved to the database and applied to every past and future "
             f"transaction from that merchant. **{db.correction_count(conn)}** correction(s) made so far.")
    cats = sorted(set(tx.category.unique().tolist() + ["Uncategorized"]))
    ed = st.data_editor(q[["id", "date", "narration", "amount", "category", "confidence"]], column_config={
            "id": None, "category": st.column_config.SelectboxColumn(options=cats), "date": st.column_config.DateColumn(disabled=True)},
            disabled=["date", "narration", "amount", "confidence"], width="stretch", key="editor")
    if st.button("Apply fixes", type="primary") and len(q):
        changed = ed.category != q.category
        if changed.any():
            for _, row in ed[changed].iterrows():
                old = q.loc[row.id == q.id, "category"].iloc[0]
                db.apply_correction(conn, int(row.id), q.loc[row.id == q.id, "merchant"].iloc[0], old, row.category)
            fresh = db.load_statement(conn, statement_id) if scope == "Latest upload" else pd.read_sql(
                "SELECT * FROM transactions ORDER BY date", conn, parse_dates=["date"])
            refl = flag_anomalies(fresh.drop(columns=["is_anomaly", "flag_reasons"]))
            db.update_anomaly_flags(conn, refl[["id", "is_anomaly", "flag_reasons"]])
            st.success(f"Saved {int(changed.sum())} correction(s)."); st.rerun()
        else:
            st.info("Nothing changed.")

with t6:
    st.caption("Runs directly against `data/finance.db`. Read-only - only a single SELECT is allowed.")
    examples = {
        "Spend by category": "SELECT category, ROUND(SUM(amount),0) AS total, COUNT(*) AS n FROM transactions WHERE direction='DR' GROUP BY category ORDER BY total DESC",
        "Monthly income vs spend": "SELECT month, SUM(CASE WHEN direction='CR' THEN amount ELSE 0 END) AS income, SUM(CASE WHEN direction='DR' THEN amount ELSE 0 END) AS spend FROM transactions GROUP BY month ORDER BY month",
        "Top 10 payees": "SELECT merchant, category, ROUND(SUM(amount),0) AS total FROM transactions WHERE direction='DR' GROUP BY merchant, category ORDER BY total DESC LIMIT 10",
        "How many corrections per category": "SELECT new_category, COUNT(*) AS fixes FROM category_corrections GROUP BY new_category ORDER BY fixes DESC",
        "Flagged transactions": "SELECT date, merchant, amount, category, flag_reasons FROM transactions WHERE is_anomaly=1 ORDER BY date DESC",
    }
    pick = st.selectbox("Example query", list(examples))
    sql = st.text_area("SQL", examples[pick], height=90)
    if st.button("Run query"):
        try: st.dataframe(db.run_select(conn, sql), width="stretch")
        except Exception as e: st.error(str(e))

with t7:
    mt = json.loads(METRICS_PATH.read_text()) if METRICS_PATH.exists() else None
    if mt and "unseen_merchants" in mt:
        u = mt["unseen_merchants"]
        st.markdown("Measured on the synthetic statement, against labels the model never saw.")
        cc = st.columns(3)
        cc[0].metric("Payees it has seen before (F1)", mt["full_system_macro_f1"]); cc[1].metric("Brand-new payees (F1)", u["full_system_macro_f1"])
        cc[2].metric("New payees auto-labelled", f"{u['auto_categorised_share']:.0%}", f"{u['accuracy_when_categorised']:.0%} accurate")
        st.caption(f"ML alone on brand-new payees scores {u['ml_only_macro_f1']}. Rules + ML + a review queue is what makes the system dependable. Real bank data is messier than this synthetic set, so expect lower numbers on your own statement.")
        st.dataframe(pd.DataFrame(mt["per_class"]).T.round(2), width="stretch")
        st.write("Example mistakes"); st.dataframe(pd.DataFrame(mt["sample_errors"]), hide_index=True, width="stretch")
    else: st.info("Run `python -m src.pipeline` to generate model metrics.")
