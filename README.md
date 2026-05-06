# VectorBT Pro Dashboard

A full-stack quantitative backtesting platform tailored for the Indian Market. It leverages [VectorBT](https://vectorbt.dev/) for high-performance vectorized backtesting and integrates natively with the **Fyers API** for fetching historical market data, featuring a seamless fallback to `yfinance`. 

The frontend is a modern, responsive dashboard built with **Next.js**, **TailwindCSS**, and **Recharts**.

## 🌟 Features
- 🚀 **High-Speed Backtesting**: Powered by VectorBT's vectorized engine.
- 📈 **Indian Market Data**: Direct integration with Fyers API (v3) for accurate historical OHLCV data.
- 🎨 **Beautiful UI**: Modern Next.js dashboard with interactive equity curves, drawdown charts, and a trade log.
- 🔐 **Automated Auth**: Built-in helper script to easily generate and refresh Fyers access tokens.
- ⚙️ **Dynamic Strategies**: Pluggable strategy system allowing you to easily add new algorithmic trading strategies.

---

## 🛠 Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- A **Fyers API account** (Get your `client_id` and `secret_key` from the [Fyers API Dashboard](https://api-dashboard.fyers.in/)).

---

## 🚀 Setup Instructions

### 1. Backend Setup (FastAPI & VectorBT)

Open a terminal and navigate to the root directory.

```bash
# Move to the backend folder
cd backend

# Create and activate a virtual environment
python -m venv venv

# On Windows:
.\venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Fyers API Authentication
1. In the `backend` folder, create a `.env` file (if it doesn't exist) with your Fyers credentials:
```env
FYERS_APP_ID=YOUR_APP_ID-100
FYERS_SECRET_KEY=YOUR_SECRET_KEY
FYERS_REDIRECT_URI=https://trade.fyers.in/api-login/redirect-uri/index.html
FYERS_ACCESS_TOKEN=
```
2. Run the provided helper script to generate your Access Token:
```bash
python fyers_auth_helper.py
```
3. Follow the instructions in the terminal. The script will automatically open your browser to log in to Fyers, ask for the `auth_code`, and update your `.env` file with a valid access token.

#### Start the Backend Server
From the **root of the project** (the `vectorBT` folder), run:
```bash
# We run from the root to ensure module imports (like `backend.main`) resolve correctly
.\backend\venv\Scripts\python.exe -m uvicorn backend.main:app --reload

# Or if activated:
python -m uvicorn backend.main:app --reload
```
The API will run at `http://127.0.0.1:8000`.

---

### 2. Frontend Setup (Next.js)

Open a **new terminal** and navigate to the frontend directory:

```bash
cd frontend

# Install Node.js dependencies
npm install

# Start the development server
npm run dev
```

The frontend dashboard will be available at [http://localhost:3000](http://localhost:3000).

---

## 🏗 Project Structure

- `/backend` - FastAPI server, VectorBT execution engine, and Fyers API client.
- `/frontend` - Next.js React application, UI components, charts, and metrics cards.
- `/strategies` - Custom Python trading strategies loaded dynamically by the backend (e.g., `sma_crossover.py`).
