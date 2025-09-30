#!/usr/bin/env python3
"""
Fix September dates for Job Dashboard - The Growth Desk sheet
The backup table has wrong dates ("September Sep") but the clean CSV has correct dates.
"""

import pandas as pd
import numpy as np

# Read the complete backup data
print("📖 Reading complete backup data...")
backup_df = pd.read_csv('./storage/production/september_complete_details.csv')

# Read the clean CSV with correct dates
print("📖 Reading clean CSV with correct dates...")
clean_df = pd.read_csv('./storage/production/clean_september_output.csv')

print(f"Backup data: {len(backup_df)} rows")
print(f"Clean data: {len(clean_df)} rows")

# Create URL to date mapping from clean CSV
url_to_date = {}
for _, row in clean_df.iterrows():
    url = row['url']
    date = row['date_in_source'].replace('"', '')  # Remove quotes
    url_to_date[url] = date

print(f"📅 Created date mapping for {len(url_to_date)} URLs")

# Fix the dates in backup data
fixed_count = 0
for i, row in backup_df.iterrows():
    url = row['url']
    sheet = row['sheet_name']
    current_date = row['date_in_source']
    
    # Fix Growth Desk sheet dates
    if sheet == 'Job Dashboard - The Growth Desk' and current_date == 'September Sep':
        if url in url_to_date:
            backup_df.at[i, 'date_in_source'] = url_to_date[url]
            fixed_count += 1

print(f"✅ Fixed {fixed_count} dates for Growth Desk sheet")

# Save corrected CSV
output_path = './storage/production/september_complete_details_FIXED.csv'
backup_df.to_csv(output_path, index=False)

print(f"💾 Saved corrected data to: {output_path}")

# Show summary
print("\n📊 SUMMARY BY SHEET:")
summary = backup_df.groupby('sheet_name').agg({
    'date_in_source': lambda x: len(x.unique()),
    'id': 'count'
}).rename(columns={'date_in_source': 'unique_dates', 'id': 'total_urls'})

for sheet, data in summary.iterrows():
    print(f"   {sheet}: {data['total_urls']} URLs, {data['unique_dates']} unique dates")

# Show sample of fixed Growth Desk dates
print(f"\n📋 SAMPLE FIXED GROWTH DESK DATES:")
growth_desk_sample = backup_df[backup_df['sheet_name'] == 'Job Dashboard - The Growth Desk']['date_in_source'].value_counts().head(10)
for date, count in growth_desk_sample.items():
    print(f"   {date}: {count} URLs")