"""Generate a realistic, MESSY UPI/bank statement (12 months) + hidden ground truth.

Why synthetic? Your real statement is private. This mimics real-world mess:
mixed narration formats, random casing, comma-formatted amounts, unknown local shops.
Ground truth is saved separately so we can honestly measure the ML model.
"""
import random, numpy as np, pandas as pd
from datetime import date, timedelta

rng = random.Random(42); nrng = np.random.default_rng(42)

# category -> (merchants, (median amount, spread), txns per month)
MERCH = {
 "Food": (["SWIGGY", "ZOMATO", "DOMINOS PIZZA", "STARBUCKS", "SRI SAI TIFFIN CENTER", "MTR RESTAURANT", "CHAI POINT", "KAMAT HOTEL", "BURGER KING"], (320, .55), 14),
 "Groceries": (["BIGBASKET", "BLINKIT", "ZEPTO", "DMART", "KRISHNA PROVISION STORES", "NANDINI MILK PARLOUR", "RELIANCE FRESH", "LAKSHMI VEGETABLES"], (450, .6), 9),
 "Transport": (["UBER INDIA", "OLA CABS", "RAPIDO", "BMTC BUS PASS", "NAMMA METRO BMRCL", "IRCTC", "REDBUS", "INDIAN OIL PETROL PUMP"], (180, .8), 10),
 "Shopping": (["AMAZON PAY", "FLIPKART", "MYNTRA", "AJIO", "DECATHLON", "CROMA ELECTRONICS", "SHREE GARMENTS"], (1200, .9), 4),
 "Bills & Utilities": (["AIRTEL PREPAID", "JIO RECHARGE", "BESCOM ELECTRICITY", "ACT FIBERNET", "BWSSB WATER", "TATA PLAY"], (600, .5), 2),
 "Entertainment": (["NETFLIX", "SPOTIFY", "BOOKMYSHOW", "PVR CINEMAS", "HOTSTAR", "STEAM GAMES"], (350, .6), 2),
 "Health": (["APOLLO PHARMACY", "MEDPLUS", "PHARMEASY", "MANIPAL HOSPITAL", "SRI VENKATESHWARA MEDICALS"], (500, .8), 2),
 "Education": (["UDEMY", "COURSERA", "NPTEL", "COLLEGE FEES ATRIA", "SAPNA BOOK HOUSE"], (900, .9), 1),
 "Investments": (["ZERODHA", "GROWW", "MUTUAL FUND SIP HDFC", "PPF SBI"], (3000, .1), 1),
}
SUBS = {"NETFLIX": 649, "SPOTIFY": 119, "HOTSTAR": 299, "AIRTEL PREPAID": 599, "ACT FIBERNET": 1049, "JIO RECHARGE": 349}
SUBCAT = {"NETFLIX": "Entertainment", "SPOTIFY": "Entertainment", "HOTSTAR": "Entertainment", "AIRTEL PREPAID": "Bills & Utilities", "ACT FIBERNET": "Bills & Utilities", "JIO RECHARGE": "Bills & Utilities"}
PEOPLE = ["RAHUL KUMAR", "PRIYA SHARMA", "MOHAMMED IRFAN", "ANITHA R", "SURESH GOWDA", "KAVYA NAIR", "ARJUN REDDY", "DEEPA MURTHY"]
BANKS = ["HDFC", "ICIC", "SBIN", "UTIB", "PUNB", "YESB"]
HANDLES = ["ybl", "okaxis", "paytm", "oksbi", "okhdfcbank", "ibl"]

def ref(): return "".join(rng.choice("0123456789") for _ in range(12))

def narration(merchant, credit=False, kind="UPI"):
    d = "CR" if credit else "DR"; r = ref(); b = rng.choice(BANKS); h = rng.choice(HANDLES)
    slug = merchant.lower().replace(" ", "")
    fmt = rng.randint(0, 5)
    if kind == "NEFT": return f"NEFT-{b}N{r[:8]}-{merchant}-SALARY"
    if fmt == 0: return f"UPI/{d}/{r}/{merchant}/{b}/{slug}@{h}"
    if fmt == 1: return f"UPI-{merchant}-{slug}@{h}-{b}0001234-{r}-UPI"
    if fmt == 2: return f"UPI/{r}/{d}/{merchant.title()}/{b}Bank"
    if fmt == 3: return f"upi/{d.lower()}/{r}/{merchant.lower()}/{slug[:8]}@{h}"
    if fmt == 4: return f"UPI/P2M/{r}/{merchant}  /Payment from PhonePe"
    return f"UPI/{d}/{r}/{merchant[:14]}/{h}/UPI"

rows, truth = [], []
start = date(2025, 10, 1)
def add(dt, narr, amt, credit, cat, anomaly=0):
    rows.append([dt, narr, amt, credit]); truth.append([cat, anomaly])

for m in range(12):
    y, mo = (start.year + (start.month - 1 + m) // 12, (start.month - 1 + m) % 12 + 1)
    first = date(y, mo, 1)
    add(first, narration("TECHNOVA SOLUTIONS PVT LTD", True, "NEFT"), 52000 + rng.choice([0, 0, 2000]), True, "Income")
    add(first + timedelta(days=4), narration("SRI MANJUNATH REALTORS"), 14500, False, "Rent")
    if mo in (1, 4, 7, 10): add(first + timedelta(days=9), f"INT.PD:{first:%d-%m}-SAVINGS INTEREST CREDIT", round(rng.uniform(310, 480), 2), True, "Income")
    for k, (sm, price) in enumerate(SUBS.items()):
        add(first + timedelta(days=6 + 3 * k + rng.randint(0, 1)), narration(sm), float(price), False, SUBCAT[sm])
    for cat, (ms, (med, spread), n) in MERCH.items():
        ms = [x for x in ms if x not in SUBS]
        for _ in range(max(0, n + rng.randint(-2, 2))):
            mer = rng.choice(ms); amt = round(float(nrng.lognormal(np.log(med), spread * .6)), 2)
            if cat == "Investments": amt = float(rng.choice([2000, 3000, 5000]))
            add(first + timedelta(days=rng.randint(0, 27)), narration(mer), min(max(amt, 10), 8000), False, cat)
    for _ in range(rng.randint(4, 7)):   # people: round-ish amounts, some come back as credits
        credit = rng.random() < .3; amt = float(rng.choice([100, 200, 250, 500, 800, 1000, 1500, 2000]))
        add(first + timedelta(days=rng.randint(0, 27)), narration(rng.choice(PEOPLE), credit), amt, credit, "Transfers")

# inject anomalies (so we can measure detection recall)
for _ in range(8):
    cat = rng.choice(["Shopping", "Food", "Health", "Entertainment", "Groceries"]); mer = rng.choice(MERCH[cat][0])
    add(start + timedelta(days=rng.randint(10, 340)), narration(mer), float(rng.choice([6200, 7400, 8900, 9800, 12750])), False, cat, 1)
for _ in range(4):   # duplicate charge, same day, same merchant + amount
    i = rng.choice([k for k, t in enumerate(truth) if t[0] in ("Food", "Shopping", "Transport") and not rows[k][3]])
    dt, n, a, c = rows[i]; add(dt, n, a, c, truth[i][0], 1)

df = pd.DataFrame(rows, columns=["date", "narration", "amt", "is_credit"]); tr = pd.DataFrame(truth, columns=["true_category", "injected_anomaly"])
order = df.sort_values("date", kind="stable").index; df, tr = df.loc[order].reset_index(drop=True), tr.loc[order].reset_index(drop=True)

# build a messy bank-style statement
bal, out = 25000.0, []
for i, r in df.iterrows():
    bal += r.amt if r.is_credit else -r.amt
    out.append({"Txn Date": r.date.strftime(rng.choice(["%d/%m/%Y", "%d-%m-%Y", "%d %b %Y"])) if i % 50 == 0 else r.date.strftime("%d/%m/%Y"),
                "Description": r.narration, "Ref No": ref() if rng.random() > .05 else "",
                "Withdrawal": "" if r.is_credit else f"{r.amt:,.2f}", "Deposit": f"{r.amt:,.2f}" if r.is_credit else "",
                "Balance": f"{bal:,.2f}"})
pd.DataFrame(out).to_csv("data/sample_statement.csv", index=False)
pd.concat([pd.DataFrame(out)[["Description"]], tr], axis=1).to_csv("data/ground_truth.csv", index=False)
print(f"{len(out)} transactions -> data/sample_statement.csv (+ data/ground_truth.csv for evaluation only)")
