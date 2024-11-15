import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import date, datetime
import requests
import seaborn as sns
import random as rd

class APIKeyManager:
    def __init__(self, api_keys, call_limit_per_key=25):

        self.api_keys = api_keys
        self.call_limit_per_key = call_limit_per_key
        self.call_counts = [0] * len(api_keys) 
        self.current_key_index = 0 

    def get_current_key(self):
        return self.api_keys[self.current_key_index]

    def increment_call_count(self):
        self.call_counts[self.current_key_index] += 1

        if self.call_counts[self.current_key_index] >= self.call_limit_per_key:
            self.switch_key()

    def switch_key(self):

        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        print(f"Switched to API key: {self.get_current_key()}")

    def is_key_exhausted(self, response):
        """
        Check if the response contains the exhaustion message from Alpha Vantage.
        """
        if "Information" in response and "API rate limit is 25 requests per day" in response["Information"]:
            return True
        return False

    def make_api_call(self, api_function, fundamental):
        """
        Wrap your actual API call within this function.
        It will automatically handle the round-robin logic.
        :param api_function: The function that makes the actual API call.
        :param args: The arguments for the API function.
        :param kwargs: The keyword arguments for the API function.
        :return: The response from the API call.
        """
        while True:
            response = api_function(fundamental, self.get_current_key())
            if self.is_key_exhausted(response):
                print(f"API key {self.get_current_key()} is exhausted.")
                self.switch_key() 
            else:
                self.increment_call_count()
                return response

api_keys =["0Y9RNTHSXLQQMDNT" , "W9AJT2712PUCRXZ8" , "SBV389KO8NIE9TIY" , "HXHP2SYKSMRS2K17"]

key_manager = APIKeyManager(api_keys)

class api_util:
    def __init__(self, ticker):
        self.ticker = ticker

    def callapi(self, fundamental, api_key):
        url = f'https://www.alphavantage.co/query?function={fundamental}&symbol={self.ticker}&apikey={api_key}'
        r = requests.get(url)
        data = r.json()
        return data

    def finances(self, fundamental = 'INCOME_STATEMENT'):
        data = key_manager.make_api_call(self.callapi, fundamental)
        finance_data = pd.DataFrame.from_dict(data['quarterlyReports']).transpose()
        finance_data.columns = finance_data.iloc[0]
        finance_data = finance_data[2:]
        finance_data.columns = [datetime.strptime(date, '%Y-%m-%d') for date in finance_data.columns]
        finance_data.columns = [date.strftime('%Y-%m') for date in finance_data.columns]
        finance_data = finance_data.transpose()
        index_val = pd.to_datetime(finance_data.index)
        finance_data['quarter'] = index_val.quarter
        finance_data['year'] = index_val.year
        finance_data.index = [f'{finance_data["year"][i]}-{finance_data["quarter"][i]}' for i in range(len(finance_data["year"]))]
        finance_data = finance_data.drop(columns = ['year', 'quarter'])
        self.finance = finance_data.transpose()
        return self.finance

    def fin_comb(self):
        i_s = self.finances('INCOME_STATEMENT').transpose()
        b_s = self.finances('BALANCE_SHEET').transpose()
        c_f = self.finances('CASH_FLOW').transpose()
        c_f = c_f.drop(columns = ['netIncome'])
        fin_com = c_f.join([b_s, i_s])
        for col in fin_com.columns:
            fin_com[col].replace('None', 0, inplace = True)
            try:
                fin_com[col] = pd.to_numeric(fin_com[col])
            except:
                fin_com.drop(columns = [col], inplace = True)
        self.fin_com = fin_com
        return self.fin_com

    def stocks(self):
        data = key_manager.make_api_call(self.callapi, 'TIME_SERIES_MONTHLY')
        ticker_data = pd.DataFrame.from_dict(data['Monthly Time Series']).transpose()
        ticker_data.index = [datetime.strptime(date, '%Y-%m-%d') for date in ticker_data.index]
        ticker_data.index = [date.strftime('%Y-%m') for date in ticker_data.index]
        ticker_data = pd.DataFrame(pd.to_numeric(ticker_data['1. open']))
        ticker_data.columns  = ['Stock Price']
        indices = pd.to_datetime(ticker_data.index)
        ticker_data['quarter'] = indices.quarter
        ticker_data['year'] = indices.year
        ticker_data = ticker_data.groupby(['year', 'quarter']).mean()
        ticker_data.index = [f'{date[0]}-{date[1]}' for date in ticker_data.index]
        self.stock = ticker_data
        return self.stock

    def fundamentals(self, from_year, from_quarter):
        comb = self.fin_comb()
        stock = self.stocks()
        for col in comb.columns:
            comb[col].replace('None', 0, inplace = True)
            try:
                comb[col] = pd.to_numeric(comb[col])
            except:
                comb.drop(columns = [col], inplace = True)
        from_year_quarter = f'{from_year}-{from_quarter}'
        fund = {}
        first_date = comb.index[0]
        fund['gross profit margin'] = (comb['grossProfit'] / comb['totalRevenue'])
        fund['operating profit margin'] = (comb['operatingIncome'] / comb['totalRevenue'])
        fund['net profit margin'] = (comb['netIncome'] / comb['totalRevenue'])
        fund['return on assets'] = (comb['netIncome'] / comb['totalAssets'])
        fund['return on equity'] = (comb['netIncome'] / comb['totalShareholderEquity'])
        fund['current ratio'] = (comb['totalCurrentAssets'] / comb['totalCurrentLiabilities'])
        fund['debt-to-equity ratio'] = (comb['totalLiabilities'] / comb['totalShareholderEquity'])
        fund['debt-to-assets ratio'] = (comb['totalLiabilities'] / comb['totalAssets'])
        fund['interest coverage ratio'] = (comb['operatingIncome'] / comb['interestExpense'])
        fund['asset turnover ratio'] = (comb['totalRevenue'] / comb['totalAssets'])
        fund['inventory turnover ratio'] = (comb['grossProfit'] / comb['inventory'])
        fund['eps'] = (comb['netIncome']-comb['dividendPayoutPreferredStock'])/comb['commonStockSharesOutstanding']
        fund['eps growth'] = fund['eps'].pct_change()
        fund['revenue growth'] = comb['totalRevenue'].pct_change()
        fund['pe'] = (stock['Stock Price'].loc[first_date:] / fund['eps'])
        fund['pb'] = (stock['Stock Price'].loc[first_date:]) / (comb['totalShareholderEquity']/comb['commonStockSharesOutstanding'])
        cols = []
        vals = []
        date = []
        for key, value in fund.items():
            cols.append(key)
            vals.append(list(value))
            date = value.index

        fund_df = pd.DataFrame(vals).transpose()
        fund_df.columns = cols
        fund_df.index = date
        fund_df = fund_df.fillna(0)
        fund_df = fund_df.loc[from_year_quarter:]
        return fund_df   

def make_heatmap(ticker, from_year, from_quarter):
    try:
        obj = api_util(ticker)
        obj_fundamentals = obj.fundamentals(from_year, from_quarter)
        obj_stock = obj.stocks()
        
        # Ensure we have data
        if obj_fundamentals.empty or obj_stock.empty:
            raise ValueError("No data retrieved for fundamentals or stock prices")
            
        merger = pd.merge(obj_stock, obj_fundamentals, left_index=True, right_index=True)
        
        # Create lagged fundamentals
        obj_fundamentals_lagged = obj_fundamentals.shift(1)
        merger_lagged = pd.merge(obj_stock, obj_fundamentals_lagged, left_index=True, right_index=True)
        
        # Calculate correlations
        corr = merger.corr()
        corr_lagged = merger_lagged.corr()
        
        # Create masks for upper triangle
        mask = np.triu(np.ones_like(corr, dtype=bool))
        corr = corr.mask(mask)
        
        mask_lagged = np.triu(np.ones_like(corr_lagged, dtype=bool))
        corr_lagged = corr_lagged.mask(mask_lagged)
        
        # Ensure we're only using the ratios we want
        corr = corr.loc[ratios, ratios]
        corr_lagged = corr_lagged.loc[ratios, ratios]
        
        print(f"Generated heatmaps for {ticker}")  # Debug log
        return corr, corr_lagged
        
    except Exception as e:
        print(f"Error in make_heatmap: {str(e)}")  # Debug log
        raise

ratios = [
    "Stock Price",
"gross profit margin",
"operating profit margin",
"net profit margin",
"return on assets",
"return on equity",
"current ratio",
"debt-to-equity ratio",
"debt-to-assets ratio",
"interest coverage ratio",
"asset turnover ratio",
"inventory turnover ratio",
"eps",
"eps growth",
"revenue growth",
"pe",
"pb"
]