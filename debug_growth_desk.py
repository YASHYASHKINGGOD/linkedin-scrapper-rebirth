#!/usr/bin/env python3
"""
Debug Growth Desk Sheet Structure
"""

import os
import sys
sys.path.insert(0, 'src')
from src.clients.google_sheets import GoogleSheetsClient

# Setup environment
env_vars = {
    "GOOGLE_OAUTH_CLIENT_JSON": "./client_secret_28309019366-uep6ho3i3k5096d1od4fo8gp1c1tj375.apps.googleusercontent.com.json",
    "GOOGLE_OAUTH_TOKEN_JSON": "./.secrets/google_token.json",
    "GOOGLE_OAUTH_REDIRECT_PORT": "8765"
}

for key, value in env_vars.items():
    if key not in os.environ:
        os.environ[key] = value

def main():
    client = GoogleSheetsClient()
    
    sheet_id = "1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q"
    tab_name = "September (2025)"
    
    print(f"🔍 Debugging Growth Desk sheet: {tab_name}")
    
    values = client.get_values(sheet_id, tab_name)
    print(f"Retrieved {len(values)} rows")
    
    print("\n📋 First 10 rows:")
    for i, row in enumerate(values[:10]):
        print(f"Row {i+1}: {row}")
        
    print("\n🔍 Looking for LinkedIn URLs in first 50 rows...")
    for i, row in enumerate(values[:50]):
        for j, cell in enumerate(row):
            if cell and "linkedin.com" in str(cell):
                print(f"Found LinkedIn URL at Row {i+1}, Col {j+1}: {cell}")
                print(f"  Full row: {row}")
                break

if __name__ == "__main__":
    main()