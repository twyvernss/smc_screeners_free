import requests
from bs4 import BeautifulSoup as bs
import pandas as pd
from django.shortcuts import render
from django.http import HttpResponse
from datetime import datetime
import pytz

# =========================
# Screener definitions
# =========================
SCREENER_CONDITIONS = {
    "momentum_compression": {
        "name": "10 Year IPO Setups",
        "condition": {
            "scan_clause": "( {cash} ( ( {cash} ( latest close / 1 month ago close > 1.2 and market cap > 0 and latest max( 3 , latest high ) / latest min( 3 , latest low ) <= 1.07 and latest volume > 5000 and market cap > 100 ) ) ) )"
        }
    },
    "ipo_3_years": {
        "name": "IPO's Listed in Last 3 Years",
        "condition": {
            "scan_clause": "( {cash} ( ( {cash} ( latest volume > 10000 and market cap > 500 and( {cash} not( 800 days ago close > 0 ) ) ) ) and latest close >= 1 day ago max( 252 , latest high ) * 0.75 and latest close <= 1 day ago max( 252 , latest high ) ) )"
        }
    },
    "ipo_1_year": {
        "name": "Recent IPOs: Last 1 Year",
        "condition": {
            "scan_clause": "( {cash} ( latest volume > 10000 and market cap > 500 and( {cash} not( 250 days ago close > 0 ) ) ) )"
        }
    },
    "all_tradable_stocks": {
        "name": "All Tradable Stocks",
        "condition": {
            "scan_clause": "( {cash} ( latest close > 25 and latest close <= 10000 and market cap >= 300 and latest {custom_indicator_176230_start}\"(  sma(  close , 50 ) *  sma(  volume , 50 ) ) / 10000000\"{custom_indicator_176230_end} >= 5 ) )"
        }
    },
    "smc_tradable_universe_near_ath": {
        "name": "SMC Tradable Universe: 25% Near ATH Stocks",
        "condition": {
            "scan_clause": "( {cash} ( latest close >= 10 years ago high * 0.75 and market cap >= 500 and latest close > 20 and latest volume > 5000 and latest close > latest \"wma( ( ( 2 * wma( (latest close), 100) ) - wma((latest close), 200) ), 14)\" and latest close > latest \"wma( ( ( 2 * wma( (latest close), 25) ) - wma((latest close), 50) ), 7)\" ) )"
        }
    },
    "minervini_stage_2": {
        "name": "Minervini Stage 2 Stocks",
        "condition": {
            "scan_clause": "( {cash} ( ( {cash} ( latest close > latest ema( close,50 ) and latest ema( close,50 ) > latest ema( close,150 ) and latest ema( close,150 ) > latest ema( close,200 ) and latest close >= 1.33 * weekly min( 52 , weekly low ) and latest close * 1.43 >= weekly max( 52 , weekly high ) and latest ema( close,200 ) > 1 month ago ema( close,200 ) and latest close >= 25 and latest volume > 1000 and latest close > 1 day ago min( 504 , latest low ) * 1.5 ) ) ) )"
        }
    },
}

# =========================
# Category mapping
# =========================
SCREENER_CATEGORIES = {
    
    "Tradable Universe": [
        "minervini_stage_2",
        "smc_tradable_universe_near_ath",
        "all_tradable_stocks"
    ],
    "IPO Base": [
        "ipo_1_year",
        "ipo_3_years",
        "momentum_compression"
    ],

}

# =========================
# Main index view
# =========================
def index(request):
    stock_list = None
    last_updated = None
    selected_screener = request.POST.get("screener_name")
    selected_screener_name = ""
    selected_category = request.GET.get("category")

    # Show screeners by category
    if selected_category and selected_category in SCREENER_CATEGORIES:
        filtered_screeners = {
            key: SCREENER_CONDITIONS[key]
            for key in SCREENER_CATEGORIES[selected_category]
            if key in SCREENER_CONDITIONS
        }
    else:
        # Default: show all
        filtered_screeners = SCREENER_CONDITIONS

    # Run scan if user selects screener
    if request.method == "POST" and selected_screener:
        screener = SCREENER_CONDITIONS.get(selected_screener)
        selected_screener_name = screener["name"] if screener else ""
        condition = screener["condition"] if screener else {}

        url = "https://chartink.com/screener/process"
        try:
            with requests.session() as s:
                r_data = s.get(url)
                soup = bs(r_data.content, "lxml")
                meta = soup.find("meta", {"name": "csrf-token"})
                header = {"x-csrf-token": meta["content"]} if meta else {}

                response = s.post(url, headers=header, data=condition)
                data = response.json()
                raw_data = data["data"]

                filtered_data = [
                    row for row in raw_data
                    if all(k in row for k in ["nsecode", "per_chg", "close", "volume", "sr"])
                ]

                stock_list = pd.DataFrame(filtered_data).rename(columns={
                    "nsecode": "stock_name",
                    "per_chg": "percent_change",
                    "close": "current_price",
                    "volume": "trade_volume",
                    "sr": "rank"
                }).to_dict(orient="records")

                last_updated = datetime.now(pytz.timezone('Asia/Kolkata'))

        except Exception as e:
            print(f"Error: {e}")
            stock_list = []

    return render(request, 'stock_app/index.html', {
        'stock_list': stock_list,
        'last_updated': last_updated,
        'screeners': filtered_screeners,
        'selected_screener': selected_screener,
        'selected_screener_name': selected_screener_name,
        'categories': SCREENER_CATEGORIES.keys(),
        'selected_category': selected_category
    })

# =========================
# CSV download view
# =========================
def download_csv(request):
    selected_screener = request.GET.get("screener_name", "episodic_pivot")
    screener = SCREENER_CONDITIONS.get(selected_screener)
    condition = screener["condition"] if screener else {}

    url = "https://chartink.com/screener/process"
    try:
        with requests.session() as s:
            r_data = s.get(url)
            soup = bs(r_data.content, "lxml")
            meta = soup.find("meta", {"name": "csrf-token"})
            header = {"x-csrf-token": meta["content"]} if meta else {}

            response = s.post(url, headers=header, data=condition)
            data = response.json()
            raw_data = data["data"]

            filtered_data = [
                row for row in raw_data
                if all(k in row for k in ["nsecode", "per_chg", "close", "volume", "sr"])
            ]

            df = pd.DataFrame(filtered_data).rename(columns={
                "sr": "Rank",
                "nsecode": "Stock Symbol",
                "per_chg": "Percent Change",
                "close": "Current Price",
                "volume": "Trade Volume"
            })

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{selected_screener}_stocks.csv"'
            df.to_csv(path_or_buf=response, index=False)
            return response

    except Exception as e:
        print("CSV download error:", e)
        return HttpResponse("Error downloading CSV")
