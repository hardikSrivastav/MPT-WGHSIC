import yfinance as yf
from datetime import datetime as dt
from numpy import random
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt

class portfolio():

    def __init__(self, tickers: list, shares: dict = None, start =  dt(2020, 1, 1), end = dt(2024, 1, 1)):
        self.tickers = tickers
        self.shares = shares or {}  # Dictionary of ticker: number of shares
        self.start = start
        self.end = end
        print(self.tickers)

    def data(self):
        data = yf.download(tickers = self.tickers, start=self.start, end = self.end)['Adj Close']
        stock_pct_change = data.pct_change()
        returns = stock_pct_change.mean()
        self.pct = stock_pct_change
        return returns

    def weight_range(self, iterations= 1000):
        weights_dict = {}
        for i in range(iterations):
            weights=random.randint(5, 50, size=len(self.tickers))
            weights = weights/sum(weights)
            weights_dict[f'iter{i}'] = weights
        weights_dict = pd.DataFrame(weights_dict)
        return weights_dict

    def risk_return(self, iterations):
        if len(self.tickers) < 2:
            raise ValueError("Need at least 2 stocks to calculate portfolio metrics")
        
        init_returns = self.data()
        corr_matr = self.pct.corr()
        weights = self.weight_range(iterations)
        returns, risk, weight_tuples = {}, {}, {}
        for i, iteration in enumerate(weights.columns):
            inst_weight = weights.loc[:, iteration]
            returns[iteration] = np.dot(init_returns, inst_weight)*252
            risk[iteration] = np.sqrt(np.dot(inst_weight, np.dot(corr_matr, inst_weight.transpose())))*np.sqrt(252)
            weight_tuples[iteration] = tuple(inst_weight)
            weight_tuples[iteration] = tuple(map(lambda x: isinstance(x, float) and round(x, 2) or x, weight_tuples[iteration]))

        values = pd.DataFrame({'returns': returns, 'risk': risk, 'weights': weight_tuples})
        values['sharpe_ratio'] = values['returns']/values['risk']

        mean_sr = np.mean(values['sharpe_ratio'])
        std_sr = np.std(values['sharpe_ratio'])
        values['normalised_sharpe_ratio'] = [iter_value for iter_value in (values['sharpe_ratio'] - mean_sr)*std_sr]
        return values
    
    def make_frontier(self, iterations = 1000):
        values  = self.risk_return(iterations)
        max_sr = max(values.loc[:, 'sharpe_ratio'])
        max_sr_related_row = values.loc[:, 'sharpe_ratio'].isin([max_sr])
        n1 = values[max_sr_related_row]
        self.max_sr = n1
        low_vol = min(values.loc[:, 'risk'])
        low_vol_related_row = values.loc[:, 'risk'].isin([low_vol])
        n2 = values[low_vol_related_row]
        self.low_vol = n2
        iden = pd.DataFrame({'max sharpe' : n1.iloc[0, :], 'min risk' : n2.iloc[0, :]}).T
        values_masked = values.where(values['normalised_sharpe_ratio'] > 0)
        values_masked = values_masked.dropna()

        fig = px.scatter(values, x = 'risk', y= 'returns', color='sharpe_ratio', hover_name=values.index, hover_data="weights")
        fig.add_trace(go.Scatter(x = [iden.loc['max sharpe', 'risk']], y= [iden.loc['max sharpe', 'returns']], mode = 'markers',
                                marker_symbol = 'star', marker_size = 15, name = 'max sharpe ratio', showlegend = False))
        fig.add_trace(go.Scatter(x = [iden.loc['min risk', 'risk']], y= [iden.loc['min risk', 'returns']], mode = 'markers',
                                marker_symbol = 'star', marker_size = 15, name = "min risk", showlegend = False))

        return fig
    
    def ideal_weights(self):
        self.make_frontier()
        merged = pd.DataFrame({
            "Low Volatility": self.low_vol['weights'].iloc[0],
            "High Sharpe Ratio": self.max_sr['weights'].iloc[0]
        }, index=self.tickers)
        return merged

    def calculate_share_adjustments(self, priority='risk'):
        """Calculate how many shares to buy/sell to reach ideal weights"""
        if not self.shares:
            return None
            
        # Get current prices
        current_prices = yf.download(tickers=self.tickers, period='1d')['Adj Close'].iloc[-1]
        
        # Calculate current portfolio value
        current_values = {ticker: self.shares.get(ticker, 0) * price 
                         for ticker, price in current_prices.items()}
        total_value = sum(current_values.values())
        
        # Make sure frontier is calculated
        self.make_frontier()
        
        # Get ideal weights based on priority
        if priority != 'risk':
            ideal_weights = self.low_vol['weights'].iloc[0]
        else:  # growth/sharpe ratio case
            ideal_weights = self.max_sr['weights'].iloc[0]
        
        # Calculate target values using the actual weights
        target_values = {}
        for i, ticker in enumerate(self.tickers):
            target_values[ticker] = total_value * ideal_weights[i]
        
        # Calculate share adjustments
        adjustments = {}
        for i, ticker in enumerate(self.tickers):
            current_shares = self.shares.get(ticker, 0)
            target_shares = target_values[ticker] / current_prices[ticker]
            adjustments[ticker] = {
                'current_shares': current_shares,
                'target_shares': round(target_shares),
                'adjustment': round(target_shares - current_shares),
                'current_weight': current_values[ticker] / total_value if total_value > 0 else 0,
                'target_weight': ideal_weights[i],
                'current_value': current_values[ticker],
                'target_value': target_values[ticker]
            }
        
        return adjustments

if __name__ == '__main__':
    portfolio1 = portfolio(['pg', 'nvda', 'v', 'msft'])
    #results = portfolio1.risk_return()
    #weights = portfolio1.ideal_weights()
    portfolio1.make_frontier().show()
