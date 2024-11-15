from application import app
import psycopg2 as pg

def init_db():
    conn = pg.connect(
        database=app.config['DB_NAME'],
        user=app.config['DB_USER'],
        password=app.config['DB_PASSWORD'],
        host=app.config['DB_HOST'],
        port=app.config['DB_PORT']
    )
    cur = conn.cursor()

    # Create tables
    cur.execute('''
        CREATE TABLE IF NOT EXISTS temp_stocks (
            tick_id SERIAL PRIMARY KEY,
            ticker VARCHAR(10),
            active_since DATE,
            year INTEGER,
            quarter INTEGER,
            asset_type VARCHAR(50),
            exchange VARCHAR(20),
            shares INTEGER
        );
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_db (
            portfolio_id SERIAL PRIMARY KEY,
            efficient_portfolio TEXT
        );
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS stock_db (
            id SERIAL PRIMARY KEY,
            portfolio_id INTEGER REFERENCES portfolio_db(portfolio_id),
            ticker VARCHAR(10),
            asset_type VARCHAR(50),
            exchange VARCHAR(20),
            year INTEGER,
            quarter INTEGER,
            active_since DATE,
            weights_1 FLOAT,
            weights_2 FLOAT,
            current_shares INTEGER,
            target_shares INTEGER,
            share_adjustment INTEGER,
            current_weight FLOAT,
            target_weight FLOAT
        );
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
