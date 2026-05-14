import yfinance as yf
import pandas as pd
import time
import math
from pathlib import Path


base_dir = Path(__file__).resolve().parent
csv_path = base_dir / "company_ticker_final_p3.csv"

if not csv_path.exists():
    raise FileNotFoundError(f"company_tickers_final.csv not found at {csv_path}")


def get_latest(df, label):
    if df is not None and not df.empty and label in df.index:
        return df.loc[label].iloc[0]
    return None

def safe_calc(val):
    """Converts None or strings to 0.0 for math operations."""
    try:
        return val if isinstance(val, (int, float)) else 0.0
    except (ValueError, TypeError):
        return 0.0

def calculate_lynch_metrics(fin, pe_ratio,ttm_net_income ):
    """
    Calculates YoY growth per year, handles negative numbers, 
    and returns the average growth and Lynch PEG.
    """
    try:
        # 1. Extract and Clean Data
        growth_rates = []
        net_income_series = fin.loc["Net Income"] if "Net Income" in fin.index else None
        #TTM = fin.loc["TTM"] if "Net Income" in fin.index else None
        #print(fin.loc["TTM"])
        if net_income_series is not None and len(net_income_series) > 1:
            # yfinance is newest -> oldest. Reverse it to get [Oldest, ..., Newest]
            raw_list = net_income_series[::-1].tolist()
            #print(raw_list)
            #raw_list.append(ttm_net_income)
            # Remove NaNs and None values
            ni_list = [x for x in raw_list if x is not None and not (isinstance(x, float) and math.isnan(x))]
            #print(ni_list)
            if len(ni_list) < 2:
                return None, None, []

            # 2. Calculate Growth per Year
            growth_rates = []
            #print(len(ni_list))
            for i in range(1, len(ni_list)):
                old_val = ni_list[i-1]
                new_val = ni_list[i]
                #print(f"New Val :{new_val}, Old Val : {old_val}")
                if old_val != 0:
                    # Logic: (New - Old) / abs(Old)
                    # Using abs() ensures that a move from -500 to +400 is POSITIVE growth
                    rate = (new_val - old_val) / abs(old_val)
                    #print(f'rates : {rate}')
                    growth_rates.append(rate)
            
            # 3. Take the Average
            if growth_rates:
                
                avg_growth = (sum(growth_rates) / len(growth_rates)) * 100
            else:
                avg_growth = None
        else:
            avg_growth = None
        
        # print(f'average growth rate : {avg_growth}')
        #print(f'growth rates: {growth_rates}')
        # 4. Calculate Lynch PEG (P/E / Growth Rate)
        # Note: Growth must be positive for PEG to be meaningful in Lynch's model
        lynch_peg = pe_ratio / avg_growth if pe_ratio is not None and isinstance(pe_ratio, (int, float)) and avg_growth is not None and avg_growth > 0 else None
        
        return avg_growth, lynch_peg, growth_rates
   
    except Exception as e:
        print(f"Error in Lynch calculation: {e}")
        return None, None, []

def calculate_pillar_scores(row):
    """Assigns scores with Earnings Yield as a tie-breaker for Valuation."""
    scores = {'Overall Score':0,'Recommendation':'', 'Reasoning':[], 'Quality': 0, 'Growth': 0, 'Solvency': 0, 'Base Valuation': 0, 'Strong Valuation':0, 'Growth Trend':0 }
    
    # 1. Quality: RoC >= 15%
    #print("calculating Quality")
    if row.get('roc') and row['roc'] >= 15:
        scores['Quality'] = 1
        
    # 2. Growth: Profitability Check
    #print("Calculating Growth line 83")
    avg_g = row.get('Avg Earnings Growth Rate %')
    net_inc = row.get('Net Income')
    #print(avg_g)
    if avg_g is not None and isinstance(avg_g, (int, float)) and avg_g > 10:
        # Lynch prefers consistency: 1 point if growth is positive and earnings exist
        if net_inc is not None and isinstance(net_inc, (int, float)) and net_inc > 0 and isinstance(row.get('EPS'), (int, float)) and row.get('EPS') is not None and row.get('EPS') > 0:
            scores['Growth'] = 1
        
    # 3. Solvency: D/E < 100 and Current Ratio > 1
    de_ratio = row.get('Debt to Equity')
    de_ratio = de_ratio if isinstance(de_ratio, (int, float)) else 999
    curr_assets = row.get('Current Assets') or 0
    curr_liab = row.get('Current Liability') or 1
    if de_ratio <= 60 and (curr_assets / curr_liab) > 1:
        scores['Solvency'] = 1
        
    # 4. Valuation: Lynch PEG < 1.0 + Earnings Yield Tie-Breaker
    l_peg = row.get('Lynch PEG')
    e_yield = row.get('Earnings Yield %')
    
    # Base Valuation Pass
    
   
    # it's a "Strong Valuation"
    #g45 = row.get('GrowthYear_4_to_5')
    g34 = row.get('GrowthYear_3_to_4')
    g23 = row.get('GrowthYear_2_to_3')
    g12 = row.get('GrowthYear_1_to_2')

    #print(f"Growth34: {g34}, Growth23: {g23}, Growth12: {g12}")

    #if (isinstance(g45, (int, float)) > isinstance(g34, (int, float))):
    #    t45_trend = 4
    #else:
    #    t45_trend = 0

    if isinstance(g34, (int, float))  and g34 > 0:
        #print(f"Growth year 3 to 4 is positive: {g34}")
        t34_trend = 4 
    else:
        t34_trend = 0 

    if isinstance(g23, (int, float)) and g23 > 0 :
        #print(f"Growth year 2 to 3 is positive: {g23}")
        t23_trend = 2
    else:
        t23_trend = 0

    if  isinstance(g12, (int, float)) and g12 > 0:
        #print(f"Growth year 1 to 1 is positive: {g12}")
        t12_trend = 1 
    else:
        t12_trend = 0


    
    #growth_trend = t45_trend + t34_trend + t12_trend
    growth_trend = t34_trend + t23_trend + t12_trend

    #print(f"growth Trend: {growth_trend}")

    if growth_trend >=6:
        scores['Growth Trend'] = 0.02 # Visual indicator of a superior value
    elif growth_trend >=4:
        scores['Growth Trend'] = 0.01 # Visual indicator of a superior value
    elif growth_trend >=2:
        scores['Growth Trend'] = 0.005
    else:
        scores['Growth Trend'] = 0

    if l_peg and isinstance(l_peg, (int, float)) and l_peg < 1.0:
        scores['Base Valuation'] = 1
        # Tie-breaker: If PEG is good AND Yield is > 5% (beating average bond yields), 
    if e_yield and isinstance(e_yield, (int, float)) and e_yield > 5 and l_peg and isinstance(l_peg, (int, float)) and l_peg < 1.0:
            scores['Strong Valuation'] = 1.1 # Visual indicator of a superior value
    
 

    scores['Overall Score'] = round(scores['Quality']  + scores['Growth']  +  scores['Solvency']  + scores['Growth Trend'] + max(scores['Base Valuation'],scores['Strong Valuation']), 3)
            
  
# recommendation 
    if scores['Overall Score'] >= 4.12:
        scores['Recommendation']= "SUPERIOR BUY"
    elif scores['Overall Score'] >= 4.11:
        scores['Recommendation']= "EXCELLENT BUY"
    elif scores['Overall Score'] >= 4.1:
        scores['Recommendation']= "STRONG BUY"
    elif scores['Overall Score'] >= 3.1:
        scores['Recommendation']= "MODERATE BUY"
    elif scores['Overall Score'] >= 3:
        scores['Recommendation']= "OK BUY"
    elif scores['Overall Score'] >= 2:
         scores['Recommendation']= "HOLD"
    elif scores['Overall Score'] >= 1:
        scores['Recommendation']= "MODERATE SELL"
    else:
        scores['Recommendation']= "SELL"

    # Generate Reasoning 
    reasoning = []
        
    # PEG Analysis
    if l_peg is not None and isinstance(l_peg, (int, float)):
        if l_peg < 0.5:
            reasoning.append(f"Very Attractive PEG ratio of {l_peg:.2f} (below 1.0) - Strong Bargain Price")
        elif l_peg >= 0.5 and l_peg <= 1:
            reasoning.append(f"Attractive PEG ratio of {l_peg:.2f} (below 1.0) - Good bargain Price")
        else:
            reasoning.append(f"PEG ratio of {l_peg:.2f} suggests Overvaluation- Not a bargain buy")
    
    if e_yield is not None and isinstance(e_yield, (int, float)):
        if e_yield > 10:
            reasoning.append(f"Very attractive rate of return per share {e_yield:.2f}")
        elif e_yield > 6:
            reasoning.append(f"Moderately attractive rate of return per share {e_yield:.2f}")
        else:
            reasoning.append(f"Earnings return  {e_yield:.2f} suggests low rate of return per share")

    if row['roc'] is not None and isinstance(row['roc'], (int, float)):
        if row['roc'] > 25:
            reasoning.append(f"Very attractive Return on investment {roc:.2f} of business suggests strong quality")
        elif row['roc'] >= 15:
            reasoning.append(f"Moderately attractive Return on investment  {roc:.2f} of business suggests good quality")
        else:
            reasoning.append(f"ROI of business is not great - suggests poor quality")

    if avg_g is not None and isinstance(avg_g, (int, float)):
        if avg_g > 1000:
            reasoning.append(f"Strong avg YoY earnings growth {avg_g:.2f} in past 4 years")
        elif avg_g > 500:
            reasoning.append(f"Moderate avg YoY earnings growth {avg_g:.2f} in past 4 years")
        if avg_g > 0:
            reasoning.append(f"Low YoY earnings growth {avg_g:.2f} in past 4 years")
    else:
        reasoning.append(f"Poor earnings growth in past 4 years")
    
    if de_ratio is not None:
        if de_ratio <= 60:
            reasoning.append(f"Strong balance sheet with D/E ratio{de_ratio:.1f}")
        elif de_ratio > 60:
            reasoning.append(f"High debt with D/E ratio of {de_ratio:.1f}")
    
    if (curr_assets / curr_liab) > 1:
        reasoning.append(f"Strong balance sheet where assets is greater than liabilities")
    else:
        reasoning.append(f"Poor balance sheet where assets is lower than liabilities")

    if growth_trend >=6:
        reasoning.append(f"Fast Grower: 4 years of continuous growth")
    elif growth_trend >=4: 
        reasoning.append(f"TurnAround: Most recent year of growth")
    elif growth_trend >=2:
        reasoning.append(f"Watchful: inconsistent growth")
    else:
        reasoning.append(f"Increased Loss Trend")



   
    scores['Reasoning'] = reasoning    

    return scores

# Reasoning 


# Configuration


#tickers = ['PDD','AEM','MGCLY','B', 'RDDT', 'YELP','NTES','AU','GFI','PYPL','KGC','RMD','FOXA','FUTU','CDE','AGI','INCY','LULU','YUMC','DECK','KSPI','LPGCY','EXEL','IAG','UHS','RDY','EHC','AOS','PPC','ALV','OGC','WFRD','PEGA','PAYC','NICE','NEU','G','URBN','HLNE','CPA','TGS','FHI','LRN','MZTI','CBT','MMS','OII','CARG','DORM','FSM','CPRX','ERO','PARR','PAGS','TTAM','QLYS','YETI','ETOR','APAM','BLBD','PRDO','PSIX','GLPG','CHA','GCT','TILE','YELP','UPWK','IDT','TIGR','YALA','PXED','LIFE','YB','SCZM','NRDS','NUTX','MAKO','TASK','CINT','MDXG','CRMD','EVER','VITL','FTK','CMCL','ESEA','CSHR','EACO','SBC','ISSC','CLMB','OSPN','DCBO','IBEX','KROS','PPIH','CGEN','BUKS','JFIN','OMSE','CHCI','XYF','LGCY','PDEX','SMID','HTLM','VXRT','BDTX','BYRN','ZJK','GOAI','QTTB','BSEM','OPXS','SOGP','LFS','LFVN','MATH','ACFN','YSXT','JL','NEON','SAGT','MSGM','CHOW','ELOG','LHSW','AGRZ','ZTSTF','MASK','TSMWF','NETTF','FOX','ANNSF','GFIOF','NCSYF','ALMMF','OCANF','ZLDPF','GLPGF','AATC','ZGM','CMCLF','ZTOEF','YSHLF','YMATF','CVCCF','JELLF','SRBEF ','GEV','BEP','NEE','ETN','CEG','BE','IFNNY','WMT','SPY','ORCL','MU','NFLX','BRK-B','META','SRBEF', 'INDV', 'VTV', 'TT', 'CEG', 'INDV', 'LLY', 'ETN', 'LULU', 'ADBE','AEM','MO','AMGN','ADP','BKR','BKNG','BMY','LNG','CL','CMCSA','CVS','DELL','HCA','HLT','ITW','IBM','INTU','MAR','MCK','NFLX','NEM','PFE','PM','PG','QCOM','CRM','TMUS','CI','UBER', 'DOX', 'STX', 'WDC', 'PM', 'MOD', 'JNJ', 'LMT', 'PG', 'SCCO', 'CSCO', 'PEP', 'PFE', 'LO', 'HD', 'PFE' ]
#tickers = ['ADBE','AEM','MO', 'AMZN', 'RDY', 'INDV', 'LULU']
data_list = []
output_file = "full_final_market_analysis_p3.csv"

print("Starting 4-Pillar Analysis with Tie-Breakers...")

try:
    with csv_path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                continue
            ticker = parts[1]
            # skip header row if present
            if ticker.lower() == "ticker" or ticker.lower() == "symbol":
                continue
            try:
                print(f"Fetching: {ticker}")
                time.sleep(2)
                stock = yf.Ticker(ticker)
                bs, fin, cash, info = stock.balance_sheet, stock.financials, stock.cashflow, stock.info

                pe_ratio = info.get("trailingPE")
                #print(f"Step 1 Calling Lynch Metrics for:{t}")
            
                ttmnetinc = safe_calc(get_latest(fin, "Net Income"))
                    
                # TTM Net Income from quarterly financials
                qfin = stock.quarterly_financials
                ttm_net_income = qfin.loc["Net Income"].iloc[:4].sum() if qfin is not None and not qfin.empty and "Net Income" in qfin.index and len(qfin.columns) >= 4 else None
                    
                avg_growth, l_peg, growth_rates = calculate_lynch_metrics(fin, pe_ratio,ttm_net_income)
                #print(f"Avg growth: {avg_growth}, LPEG: {l_peg} for {t}")
                    
                # Earnings Yield 
                #print(f"calculating earings yield for {t} with pe_ratio: {pe_ratio}")
                e_yield = (1 / pe_ratio) * 100 if isinstance(pe_ratio, (int, float)) and pe_ratio > 0 else None
                #print(f"Earnings Yield {e_yield}")
                #print(f"Calculating ROC for {t}")
                roc = safe_calc(get_latest(fin, "Operating Income")) / safe_calc((get_latest(bs, "Total Assets")) - safe_calc(get_latest(bs, "Current Liabilities"))) * 100 if safe_calc(get_latest(bs, "Total Assets")) else 0
                 #print(f"roc for {t}:{roc}") 
                row = {
                    "Ticker": ticker,
                    "Name": info.get("longName"),
                    "Industry":info.get("industry"),
                    "Sector":info.get("sector"),
                    "Current Price":info.get("currentPrice"),
                    "EPS": info.get("trailingEps"),
                    "Average Analyst Rating": info.get("averageAnalystRating"),
                    "P/E Ratio": pe_ratio,
                    "Earnings Yield %": round(e_yield, 2) if e_yield else "N/A",
                    "Avg Earnings Growth Rate %": round(avg_growth, 2) if avg_growth else "N/A",
                    "Lynch PEG": round(l_peg, 2) if l_peg else "N/A",
                    "PEGRatio":info.get("pegRatio"),
                    "Trailing PEG Ratio":info.get("trailingPegRatio"),
                    "Net Income": ttmnetinc,
                    "TTM Net Income": ttm_net_income if isinstance(ttm_net_income, (int, float)) else "N/A",
                    "Operating Income": safe_calc(get_latest(fin, "Operating Income")),
                    "Total Assets": safe_calc(get_latest(bs, "Total Assets")),
                    "Debt to Equity": info.get("debtToEquity"),
                    "roc": safe_calc(get_latest(fin, "Operating Income")) / safe_calc((get_latest(bs, "Total Assets")) - safe_calc(get_latest(bs, "Current Liabilities"))) * 100 if safe_calc(get_latest(bs, "Total Assets"))        else 0,
                    "Current Assets":  safe_calc(get_latest(bs, "Current Assets")),
                    "Current Liability": safe_calc(get_latest(bs, "Current Liabilities")),
                }
                row.update({f"GrowthYear_{k+1}_to_{k+2}": val for k, val in enumerate(growth_rates)})      
                print(f"Calling pillar scores for {ticker}")
                scores = calculate_pillar_scores(row)      
                row.update(scores)
                cleaned_row = {k: (v if v is not None else "N/A") for k, v in row.items()}
            
                final_row = {
                    "Ticker": cleaned_row["Ticker"],
                    "Name":  cleaned_row["Name"],
                    "Industry":cleaned_row["Industry"],
                    "Sector":cleaned_row["Sector"],
                    "Current Price":cleaned_row["Current Price"],
                    "Overall Score":cleaned_row["Overall Score"],
                    "Recommendation":cleaned_row["Recommendation"],
                    "Reasoning":cleaned_row["Reasoning"],
                    "EPS": cleaned_row["EPS"],
                    "Average Analyst Rating": cleaned_row["Average Analyst Rating"],
                    "P/E Ratio": cleaned_row["P/E Ratio"],
                    "Earnings Yield %": cleaned_row["Earnings Yield %"],
                    "Avg Earnings Growth Rate %": cleaned_row["Avg Earnings Growth Rate %"],
                    "Lynch PEG": cleaned_row["Lynch PEG"],
                    "GrowthYear_1_to_2":cleaned_row["GrowthYear_1_to_2"],
                    "GrowthYear_2_to_3":cleaned_row["GrowthYear_2_to_3"],
                    "GrowthYear_3_to_4":cleaned_row["GrowthYear_3_to_4"],
                    #"GrowthYear_4_to_5":cleaned_row["GrowthYear_4_to_5"],
                    "Quality":cleaned_row["Quality"],
                    "Growth": cleaned_row["Growth"],
                    "Solvency": cleaned_row["Solvency"],
                    "Base Valuation": cleaned_row["Base Valuation"],
                    "Strong Valuation": cleaned_row["Strong Valuation"],
                    "Growth Trend": cleaned_row["Growth Trend"],
                    "Debt to Equity": cleaned_row["Debt to Equity"],
                    "roc": cleaned_row["roc"],
                    "Current Assets": cleaned_row["Current Assets"],
                    "Current Liability": cleaned_row["Current Liability"],
                    "Net Income": cleaned_row["Net Income"],
                    "TTM Net Income":cleaned_row["TTM Net Income"],
                    "Operating Income": cleaned_row["Operating Income"],
                }
                    
                data_list.append(final_row)

                if len(data_list) % 200 == 0:
                    pd.DataFrame(data_list).to_csv(output_file, index=False)
                    print(f"  Saved {len(data_list)} records so far...")
                    
            except Exception as e:
                print(f"Error on {ticker}: {e}")

finally:
    if data_list:
        df = pd.DataFrame(data_list)
        df.to_csv(output_file, index=False)
        print(f"\nAnalysis complete. {len(data_list)} records saved to {output_file}")
    else:
        print("\nNo data was collected.")