import os
from pathlib import Path
from fyers_apiv3 import fyersModel
from dotenv import load_dotenv, set_key
import webbrowser

# Ensure .env is loaded from the backend directory (where this script lives)
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def generate_access_token():
    client_id = os.getenv("FYERS_APP_ID")
    secret_key = os.getenv("FYERS_SECRET_KEY")
    redirect_uri = os.getenv("FYERS_REDIRECT_URI")

    if not client_id or client_id == "your_app_id":
        client_id = input("Enter your Fyers Client ID (App ID): ").strip()
    if not secret_key or secret_key == "your_secret_key":
        secret_key = input("Enter your Fyers Secret Key: ").strip()
    if not redirect_uri or redirect_uri == "your_redirect_uri":
        redirect_uri = input("Enter your Fyers Redirect URI: ").strip()

    # Step 1: Create a session model with client_id, secret_key and redirect_uri
    session = fyersModel.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type="code",
        grant_type="authorization_code"
    )

    # Step 2: Generate the auth URL
    auth_url = session.generate_authcode()
    print(f"\n1. Opening auth URL in your browser: {auth_url}")
    webbrowser.open(auth_url)
    
    print("\n2. Login to Fyers and authorize the app.")
    print("3. You will be redirected to your Redirect URI.")
    print("4. Copy the 'auth_code' from the URL (it's the value after 'auth_code=')")
    
    auth_code = input("\nEnter the auth_code here: ").strip()
    
    if not auth_code:
        print("Auth code is required.")
        return

    # Step 3: Set the auth code and generate the access token
    session.set_token(auth_code)
    response = session.generate_token()
    
    if response.get("s") == "ok":
        access_token = response.get("access_token")
        print("\nSUCCESS! Access Token generated.")
        print(f"Token: {access_token}")
        
        # Optionally update .env in backend directory
        set_key(str(ENV_PATH), "FYERS_APP_ID", client_id)
        set_key(str(ENV_PATH), "FYERS_SECRET_KEY", secret_key)
        set_key(str(ENV_PATH), "FYERS_REDIRECT_URI", redirect_uri)
        set_key(str(ENV_PATH), "FYERS_ACCESS_TOKEN", access_token)
        print(f"\nUpdated {ENV_PATH} with new credentials.")
    else:
        print(f"\nFAILED to generate access token: {response}")

if __name__ == "__main__":
    generate_access_token()
