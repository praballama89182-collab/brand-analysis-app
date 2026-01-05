import streamlit as st
import pandas as pd
import math
from io import BytesIO

# --- App Configuration ---
st.set_page_config(page_title="Brand Analysis Uplift App", layout="wide")
st.title("Brand Analysis Uplift App")
st.caption("Upload CSV → Filter Price → Deduplicate → Uplift → KPIs → Export")

# --- 1. File Upload ---
file = st.file_uploader("Upload Helium 10 Xray CSV", type=["csv"])

if file:
    # Load raw data
    df = pd.read_csv(file)
    cols = df.columns.tolist()

    # --- 2. Sidebar Settings ---
    st.sidebar.header("Step 1: Map Columns")
    brand_col   = st.sidebar.selectbox("Brand column", options=cols, index=cols.index("Brand") if "Brand" in cols else 0)
    sales_col   = st.sidebar.selectbox("Sales (Units) column", options=cols, index=cols.index("Sales") if "Sales" in cols else 0)
    revenue_col = st.sidebar.selectbox("Revenue column", options=cols, index=cols.index("Revenue") if "Revenue" in cols else 0)
    
    # Auto-detect price column (handling the double space in 'Price  ₹')
    price_default_idx = 0
    for i, col in enumerate(cols):
        if "Price" in col:
            price_default_idx = i + 1
            break
    price_col = st.sidebar.selectbox("Price Selector column", options=["<None>"] + cols, index=price_default_idx)

    st.sidebar.divider()
    st.sidebar.header("Step 2: Filter & Uplift")
    
    # Pre-clean price for slider range
    temp_work = df.copy()
    price_min, price_max = 0.0, 10000.0
    
    if price_col != "<None>":
        temp_work[price_col] = (temp_work[price_col].astype(str).str.replace(',', '', regex=False)
                                .str.extract(r'([-+]?\d*\.?\d+)')[0].astype(float))
        price_min = float(temp_work[price_col].min()) if not temp_work[price_col].isna().all() else 0.0
        price_max = float(temp_work[price_col].max()) if not temp_work[price_col].isna().all() else 10000.0
        
        # The Price Selector Slider
        selected_price_range = st.sidebar.slider(
            f"Filter by Price ({price_col})",
            min_value=0.0,
            max_value=price_max,
            value=(price_min, price_max),
            step=1.0
        )
    
    uplift_pct = st.sidebar.number_input("Uplift percentage (%)", min_value=0.0, max_value=1000.0, value=30.0, step=1.0)

    # --- 3. Preview ---
    st.markdown("**Raw Data Preview (first 10 rows):**")
    st.dataframe(df.head(10))

    if st.button("🚀 Run Brand Analysis"):
        work = df.copy()

        # Clean numerics for relevant columns
        cols_to_clean = [sales_col, revenue_col]
        if price_col != "<None>":
            cols_to_clean.append(price_col)

        for c in cols_to_clean:
            if c in work:
                work[c] = (work[c].astype(str).str.replace(',', '', regex=False)
                                 .str.extract(r'([-+]?\d*\.?\d+)')[0].astype(float))

        # Filter by Price Range if selector is used
        if price_col != "<None>":
            initial_count = len(work)
            work = work[(work[price_col] >= selected_price_range[0]) & (work[price_col] <= selected_price_range[1])]
            st.write(f"Filtered out {initial_count - len(work)} products outside price range.")

        # Remove rows with missing essential data
        work = work.dropna(subset=[brand_col, sales_col, revenue_col])

        # Deduplicate identical listings
        work = work.drop_duplicates(subset=[brand_col, revenue_col, sales_col], keep="first")

        # Aggregate by Brand
        agg = work.groupby(brand_col, as_index=False).agg(
            **{ "Sales": (sales_col, "sum"), "Revenue": (revenue_col, "sum") }
        ).rename(columns={brand_col: "Brand"})

        # Apply Uplift
        factor = 1 + uplift_pct/100.0
        agg["Units_actual"]   = (agg["Sales"]   * factor).apply(lambda x: math.ceil(x if pd.notna(x) else 0))
        agg["Revenue_actual"] = (agg["Revenue"] * factor).apply(lambda x: math.ceil(x if pd.notna(x) else 0))

        # Calculate KPIs
        agg["AOV"] = (agg["Revenue_actual"] / agg["Units_actual"]).apply(lambda x: math.ceil(x if pd.notna(x) else 0))
        
        total_units   = agg["Units_actual"].sum()
        total_revenue = agg["Revenue_actual"].sum()
        
        agg["Sales %"]   = agg["Units_actual"]   / total_units if total_units else 0
        agg["Revenue %"] = agg["Revenue_actual"] / total_revenue if total_revenue else 0

        # Sort and Add Total Row
        agg = agg.sort_values("Revenue_actual", ascending=False)
        total_row = pd.DataFrame([{
            "Brand": "TOTAL",
            "Units_actual": total_units,
            "Revenue_actual": total_revenue,
            "AOV": math.ceil(total_revenue/total_units) if total_units else 0,
            "Sales %": 1.0,
            "Revenue %": 1.0
        }])
        
        final = pd.concat([agg, total_row], ignore_index=True)[
            ["Brand", "Units_actual", "Revenue_actual", "AOV", "Sales %", "Revenue %"]
        ]

        # --- 4. Results ---
        st.markdown("### Result Table")
        st.dataframe(final)

        # Excel Export logic
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            final.to_excel(writer, index=False, sheet_name="Brand Analysis")
            wb = writer.book
            ws = writer.sheets["Brand Analysis"]
            
            # Formats
            comma = wb.add_format({"num_format": "#,##0"})
            pct   = wb.add_format({"num_format": "0.00%"})
            bold  = wb.add_format({"bold": True})
            
            ws.set_row(0, None, bold)
            ws.set_column("A:A", 30)
            ws.set_column("B:D", 16, comma)
            ws.set_column("E:F", 14, pct)

        buffer.seek(0)
        st.download_button(
            label="⬇️ Download Excel Analysis",
            data=buffer,
            file_name="Brand_Uplift_Analysis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("Upload your Helium 10 Xray CSV file to start.")
