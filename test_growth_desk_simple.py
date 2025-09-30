#!/usr/bin/env python3

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
    values = client.get_values("1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q", "September (2025)")
    
    print(f"Total rows: {len(values)}")
    print("\n=== Testing LinkedIn URL detection ===")
    
    # Look at rows 3-10 (which our debug script showed had LinkedIn URLs)
    for row_idx in range(2, 10):  # rows 3-10 (0-indexed)
        if row_idx < len(values):
            row = values[row_idx]
            print(f"\nRow {row_idx + 1}: {row}")
            
            # Check each cell for LinkedIn URL
            linkedin_found = False
            for i, cell in enumerate(row):
                if cell and "linkedin.com" in str(cell):
                    print(f"  LinkedIn URL found in column {i}: {cell}")
                    linkedin_found = True
                    
            if not linkedin_found:
                print("  NO LinkedIn URL found")

if __name__ == "__main__":
    main()