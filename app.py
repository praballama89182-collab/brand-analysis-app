
import streamlit as st
import pandas as pd
import math
from io import BytesIO

st.set_page_config(page_title="Brand Analysis Uplift App", layout="wide")
st.title("Brand Analysis Uplift App")
st.caption("Upload CSV → Clean → Deduplicate (Revenue+Sales) → Uplift → KPIs → Export Excel (no APIs)")

file = st.file_uploader("Upload Helium 10 Xray CSV", type=["csv"])

if file:
    df = pd.read_csv(file)
    st.markdown("**Preview (first 20 rows):**")
    st.dataframe(df.head(20))

    cols = df.columns.tolist()
    st.markdown("### Map Columns (if different names)")
    brand_col  = st.selectbox("Brand column", options=cols, index=cols.index("Brand") if "Brand" in cols else 0)
    sales_col  = st.selectbox("Sales (Units) column", options=cols, index=cols.index("Sales") if "Sales" in cols else 0)
    revenue_col= st.selectbox("Revenue column", options=cols, index=cols.index("Revenue") if "Revenue" in cols else 0)
    price_col  = st.selectbox("Price ₹ column (optional)", options=["<None>"] + cols, index=(cols.index("Price ₹")+1) if "Price ₹" in cols else 0)

    uplift_pct = st.number_input("Uplift percentage (%)", min_value=0.0, max_value=1000.0, value=30.0, step=1.0)
    if st.button("Run Brand Analysis"):
        work = df.copy()

        # Clean numerics
        for c in [sales_col, revenue_col] + ([] if price_col=="<None>" else [price_col]):
            if c in work:
                work[c] = (work[c].astype(str).str.replace(',', '', regex=False)
                                     .str.extract(r'([-+]?\d*\.?\d+)')[0].astype(float))

        work = work.dropna(subset=[brand_col, sales_col, revenue_col])

        # Exact duplicate pair removal: (Brand, Revenue, Sales)
        work = work.drop_duplicates(subset=[brand_col, revenue_col, sales_col], keep="first")

        # Aggregate
        agg = work.groupby(brand_col, as_index=False).agg(
            **{ "Sales": (sales_col, "sum"), "Revenue": (revenue_col, "sum") }
        ).rename(columns={brand_col: "Brand"})

        # Uplift
        factor = 1 + uplift_pct/100.0
        agg["Units_actual"]   = (agg["Sales"]   * factor).apply(lambda x: math.ceil(x if pd.notna(x) else 0))
        agg["Revenue_actual"] = (agg["Revenue"] * factor).apply(lambda x: math.ceil(x if pd.notna(x) else 0))

        # KPIs
        agg["AOV"] = (agg["Revenue_actual"] / agg["Units_actual"]).apply(lambda x: math.ceil(x if pd.notna(x) else 0))
        total_units   = agg["Units_actual"].sum()
        total_revenue = agg["Revenue_actual"].sum()
        agg["Sales %"]   = agg["Units_actual"]   / total_units if total_units else 0
        agg["Revenue %"] = agg["Revenue_actual"] / total_revenue if total_revenue else 0

        # Sort and total
        agg = agg.sort_values("Revenue_actual", ascending=False)
        import math
        total_row = pd.DataFrame([{
            "Brand": "TOTAL",
            "Units_actual": total_units,
            "Revenue_actual": total_revenue,
            "AOV": math.ceil(total_revenue/total_units) if total_units else 0,
            "Sales %": 1.0,
            "Revenue %": 1.0
        }])
        final = pd.concat([agg, total_row], ignore_index=True)[
            ["Brand","Units_actual","Revenue_actual","AOV","Sales %","Revenue %"]
        ]

        st.markdown("### Result Preview")
        st.dataframe(final)

        # Excel export
        from io import BytesIO
        import pandas as pd
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            final.to_excel(writer, index=False, sheet_name="Brand Analysis")
            wb = writer.book
            ws = writer.sheets["Brand Analysis"]
            comma = wb.add_format({"num_format": "#,##0"})
            pct   = wb.add_format({"num_format": "0.00%"})
            bold  = wb.add_format({"bold": True})
            ws.set_row(0, None, bold)
            ws.set_column("A:A", 30)
            ws.set_column("B:D", 16, comma)
            ws.set_column("E:F", 14, pct)

        buffer.seek(0)
        st.download_button("⬇️ Download Excel", data=buffer, file_name="Brand_Analysis.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.info("Upload a CSV to begin.")
