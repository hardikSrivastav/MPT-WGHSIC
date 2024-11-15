from application import app
from flask import render_template, url_for, request, redirect 
import pandas as pd 
import numpy as np
import json
import plotly 
import plotly_express as px
from application.api import *
from application.optimizer import *
from datetime import datetime as dt
import psycopg2 as pg
import redis

#r = redis.Redis(host='localhost', port=6379, db=0)
print("Redis URL:", app.config['REDIS_URL'])
r = redis.from_url(app.config['REDIS_URL'])
r.ping()  # Test connection
print("Redis connection successful")

'''
conn = pg.connect(database = "test", 
                        user = "postgres", 
                        host= 'localhost',
                        password = "hardik@321",
                        port = 5432)
'''

conn = pg.connect(
    database=app.config['DB_NAME'],
    user=app.config['DB_USER'],
    password=app.config['DB_PASSWORD'],
    host=app.config['DB_HOST'],
    port=app.config['DB_PORT']
)
cur = conn.cursor()

listings = pd.read_excel('application/AlphaVantage listings.xlsx')
listings = listings.sort_values(by = ['name'])

current_priority = 'risk'  # default value

@app.route('/', methods = ['POST', 'GET'])
def index():
    if request.method == 'POST':
        tick = request.form['ticker']
        year = int(request.form['time_year'])
        quarter = int(request.form['time_quarter'])
        shares = int(request.form['shares'])
        
        # Get the stock information
        ipo_date = listings.loc[(listings['symbol'] == tick), 'ipoDate'].iloc[0].date()
        exchange = listings.loc[(listings['symbol'] == tick), 'exchange'].iloc[0]
        asset_type = listings.loc[(listings['symbol'] == tick), 'assetType'].iloc[0]
        
        # Use parameterized query instead of f-string
        cur.execute("""
            INSERT INTO temp_stocks(ticker, active_since, year, quarter, asset_type, exchange, shares) 
            VALUES(%s, %s, %s, %s, %s, %s, %s)
        """, (tick, ipo_date, year, quarter, asset_type, exchange, shares))
        conn.commit()

        return redirect('/')
    else:
        cur.execute('SELECT * FROM temp_stocks;')
        rows = cur.fetchall()
        
        # Ensure listings DataFrame is properly loaded
        print("Listings DataFrame Info:")
        print(listings.info())
        print("\nSample of listings data:")
        print(listings.head())
        
        # Convert to dictionary and ensure all values are strings
        stocks_data = {
            'symbol': [str(x) for x in listings['symbol'].tolist()],
            'name': [str(x) for x in listings['name'].tolist()],
            'exchange': [str(x) for x in listings['exchange'].tolist()],
            'assetType': [str(x) for x in listings['assetType'].tolist()],
            'ipoDate': [x.strftime('%Y-%m-%d') if pd.notnull(x) else 'N/A' 
                       for x in listings['ipoDate']]
        }
        
        # Verify data structure
        print("\nFirst few items in stocks_data:")
        for key in stocks_data:
            print(f"{key}: {stocks_data[key][:5]}")
        
        return render_template('index.html', ticker_list=stocks_data, ticks=rows)

@app.route('/delete/<int:id>')
def delete(id):
    try:
        cur.execute("DELETE FROM temp_stocks WHERE tick_id = %s;", (id,))
        conn.commit()
        return redirect('/')
    except:
        return 'There was an error deleting your file'
        
@app.route('/plot/<int:id>')
def plotter(id):
    try:
        # Get stock data
        cur.execute('SELECT ticker, year, quarter FROM temp_stocks WHERE tick_id = %s;', (id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("No stock found with given ID")
            
        tick, year, quarter = row[0], row[1], row[2]
        print(f"Plotting heatmap for {tick} {year}-{quarter}")  # Debug log

        # Check Redis cache
        cache_key = f"{tick}_{year}_{quarter}_heatmap"
        cached_value = r.get(cache_key)

        if cached_value:
            print("Using cached data")  # Debug log
            cached_data = json.loads(cached_value)
            merger = pd.DataFrame(cached_data[0], columns=ratios, index=ratios)
            merger_lagged = pd.DataFrame(cached_data[1], columns=ratios, index=ratios)
        else:
            print("Generating new heatmap")  # Debug log
            merger, merger_lagged = make_heatmap(tick, year, quarter)
        # Store in Redis as JSON
            r.set(cache_key, json.dumps([merger.values.tolist(), merger_lagged.values.tolist()]))
        
        # Create plotly figures with updated layout
        fig1 = px.imshow(merger,
                        labels=dict(color="Correlation"),
                        title=f'Correlation Matrix of {tick}')
        fig1.update_layout({
            'xaxis_showgrid': False,
            'yaxis_showgrid': False,
            'plot_bgcolor': 'rgba(0, 0, 0, 0)',
            'paper_bgcolor': 'rgba(0, 0, 0, 0)',
            'height': 700,
            'width': 700,
            'margin': dict(l=50, r=50, t=50, b=50)
        })
        
        fig2 = px.imshow(merger_lagged,
                        labels=dict(color="Correlation"),
                        title=f'Quarterly Lagged Correlation Matrix of {tick}')
        fig2.update_layout({
            'xaxis_showgrid': False,
            'yaxis_showgrid': False,
            'plot_bgcolor': 'rgba(0, 0, 0, 0)',
            'paper_bgcolor': 'rgba(0, 0, 0, 0)',
            'height': 700,
            'width': 700,
            'margin': dict(l=50, r=50, t=50, b=50)
        })
        
        # Convert to JSON
        graph1JSON = json.dumps(fig1, cls=plotly.utils.PlotlyJSONEncoder)
        graph2JSON = json.dumps(fig2, cls=plotly.utils.PlotlyJSONEncoder)
        
        return render_template('plot.html', 
                             graph1=graph1JSON, 
                             graph2=graph2JSON)
    
    except Exception as e:
        print(f"Error in plotter: {str(e)}")  # Debug log
        return render_template('runout.html')
    
@app.route('/portfolio', methods= ['POST', 'GET'])
def portfolio_maker():
    if request.method == 'POST':
        cur.execute('SELECT ticker, asset_type, exchange, year, quarter, active_since, shares FROM temp_stocks')
        rows = cur.fetchall()
        tickers = []
        shares = {}
        for row in rows:
            tickers.append(row[0]) 
            shares[row[0]] = row[1]
        
        pf = portfolio(tickers, shares)
        weights = pf.ideal_weights()
        adjustments = pf.calculate_share_adjustments()
        weights = tuple(weights.itertuples(index=False, name=None))
        
        graph = pf.make_frontier()
        eff = json.dumps(graph, cls = plotly.utils.PlotlyJSONEncoder)
        
        # Store the portfolio and get its ID
        cur.execute(f"INSERT INTO portfolio_db(efficient_portfolio) VALUES ('{eff}') RETURNING portfolio_id;")
        portfolio_id = cur.fetchone()[0]
        conn.commit()

        # Store stock data along with adjustments
        for i, row in enumerate(rows):
            ticker = row[0]
            adj = adjustments[ticker] if adjustments else None
            
            cur.execute("""
                INSERT INTO stock_db(
                    portfolio_id, ticker, asset_type, exchange, year, quarter, 
                    active_since, weights_1, weights_2, current_shares, 
                    target_shares, share_adjustment, current_weight, target_weight
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                );
            """, (
                portfolio_id, row[0], row[1], row[2], row[3], row[4], row[5],
                weights[i][0], weights[i][1],
                adj['current_shares'] if adj else None,
                adj['target_shares'] if adj else None,
                adj['adjustment'] if adj else None,
                adj['current_weight'] if adj else None,
                adj['target_weight'] if adj else None
            ))
        conn.commit()
        return redirect('/')
    else:
        return redirect('/')
    
@app.route('/describe', methods = ['POST', 'GET'])
def describe():
    if request.method == 'POST' or request.method == 'GET':
        cur.execute('SELECT * FROM portfolio_db')
        pf = cur.fetchall()
        portfolio_item = {}
        for portfolio_items in pf:
            id = portfolio_items[0]
            graphJSON = portfolio_items[1]
            
            # Updated query to include share adjustment information
            cur.execute("""
                SELECT ticker, weights_1, weights_2, 
                       current_shares, target_shares, share_adjustment,
                       current_weight, target_weight
                FROM stock_db 
                WHERE portfolio_id = %s
            """, (id,))
            stock_tickers = cur.fetchall()
            conn.commit()
            
            formatted_portfolio = [
                {
                    'ticker': item[0],
                    'max_sharpe': item[1],
                    'low_risk': item[2],
                    'current_shares': item[3],
                    'target_shares': item[4],
                    'adjustment': item[5],
                    'current_weight': item[6],
                    'target_weight': item[7]
                } for item in stock_tickers
            ]
            portfolio_item[id] = [formatted_portfolio, graphJSON]
        return render_template('portfolio.html', 
                             ports=portfolio_item, 
                             current_priority=current_priority)
        

@app.route('/eff/<int:id>')
def frontier(id):
    try:
        # Get tickers and shares from stock_db instead of just tickers
        cur.execute("""
            SELECT ticker, current_shares 
            FROM stock_db 
            WHERE portfolio_id = %s
        """, (id,))
        rows = cur.fetchall()
        
        # Create tickers and shares dictionaries
        tickers = [row[0] for row in rows]
        shares = {row[0]: row[1] for row in rows}
        
        # Initialize portfolio with both tickers and shares
        pf = portfolio(tickers, shares)
        
        # Generate frontier plot
        obj = pf.make_frontier()
        graphJSON = json.dumps(obj, cls=plotly.utils.PlotlyJSONEncoder)
        
        # Get portfolio details
        cur.execute("""
            SELECT ticker, weights_1, weights_2, 
                   current_shares, target_shares, 
                   current_weight, target_weight 
            FROM stock_db 
            WHERE portfolio_id = %s
        """, (id,))
        stock_tickers = cur.fetchall()
        
        # Format portfolio data
        formatted_portfolio = [
            {
                'ticker': item[0],
                'max_sharpe': item[1],
                'low_risk': item[2],
                'current_shares': item[3],
                'target_shares': item[4],
                'current_weight': item[5],
                'target_weight': item[6]
            }
            for item in stock_tickers
        ]
        
        return render_template('plot_pf.html', 
                             graph=graphJSON, 
                             items=formatted_portfolio)
    
    except Exception as e:
        print(f"Error in frontier: {str(e)}")  # Add logging for debugging
        return 'There was an error plotting your portfolio'
    
@app.route('/delete_pf/<int:id>')
def delete_pf(id):
    cur.execute("DELETE FROM stock_db WHERE portfolio_id = %s;", (id,))
    cur.execute("DELETE FROM portfolio_db WHERE portfolio_id = %s;", (id,))
    conn.commit()
    return redirect('/describe')

@app.route('/update_priority', methods=['POST'])
def update_priority():
    if request.method == 'POST':
        global current_priority
        current_priority = request.form.get('priority', 'risk')
        
        # Get current portfolio
        cur.execute('SELECT ticker, shares FROM temp_stocks')
        rows = cur.fetchall()
        tickers = []
        shares = {}
        for row in rows:
            tickers.append(row[0])
            shares[row[0]] = row[1]
        
        pf = portfolio(tickers, shares)
        weights = pf.ideal_weights()
        adjustments = pf.calculate_share_adjustments(priority=current_priority)
        
        # Update the database with new calculations
        for ticker in tickers:
            adj = adjustments[ticker]
            cur.execute("""
                UPDATE stock_db 
                SET target_shares = %s,
                    share_adjustment = %s,
                    target_weight = %s
                WHERE ticker = %s
            """, (
                adj['target_shares'],
                adj['adjustment'],
                adj['target_weight'],
                ticker
            ))
        conn.commit()
        
        return redirect('/describe')