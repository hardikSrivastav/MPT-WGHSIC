from application import app
import psycopg2 as pg
import time

def init_db():
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
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
            print("Database initialized successfully!")
            break
            
        except Exception as e:
            print(f"Database initialization attempt {retry_count + 1} failed: {str(e)}")
            retry_count += 1
            if retry_count < max_retries:
                print(f"Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print("Failed to initialize database after maximum retries")
                raise

if __name__ == "__main__":
    init_db()
