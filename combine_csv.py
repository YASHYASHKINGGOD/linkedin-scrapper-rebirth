#!/usr/bin/env python3
"""
Combine multiple LinkedIn post CSV files into one master CSV
"""

import pandas as pd
import glob
import os
from datetime import datetime

def combine_csv_files(input_pattern, output_file):
    """
    Combine multiple CSV files matching the pattern into one master CSV
    """
    
    # Find all CSV files matching the pattern
    csv_files = glob.glob(input_pattern)
    csv_files = [f for f in csv_files if 'batch_summary' not in f]  # Exclude summary files
    
    if not csv_files:
        print(f"❌ No CSV files found matching pattern: {input_pattern}")
        return
    
    print(f"📁 Found {len(csv_files)} CSV files to combine:")
    
    combined_data = []
    
    for i, file in enumerate(csv_files, 1):
        print(f"   {i}. {os.path.basename(file)}")
        
        try:
            # Read each CSV
            df = pd.read_csv(file)
            combined_data.append(df)
            
        except Exception as e:
            print(f"   ❌ Error reading {file}: {e}")
            continue
    
    if not combined_data:
        print("❌ No valid CSV files found to combine")
        return
    
    # Combine all dataframes
    master_df = pd.concat(combined_data, ignore_index=True)
    
    # Add a batch_id column for tracking
    master_df['batch_id'] = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Save combined CSV
    master_df.to_csv(output_file, index=False)
    
    print(f"\n✅ Combined CSV created: {output_file}")
    print(f"📊 Total posts: {len(master_df)}")
    print(f"💬 Total comments: {master_df['comment_count'].sum()}")
    
    # Show summary by author
    print(f"\n📋 Summary by Author:")
    summary = master_df.groupby('post_author').agg({
        'comment_count': 'sum',
        'post_url': 'count'
    }).rename(columns={'post_url': 'posts'})
    
    for author, row in summary.iterrows():
        print(f"   • {author}: {row['posts']} post(s), {row['comment_count']} comments")
    
    return output_file

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Combine all LinkedIn post CSVs from today's batch
    input_pattern = "outputs/linkedin_post_20250828_143*.csv"
    output_file = f"outputs/combined_posts_{timestamp}.csv"
    
    print("🔄 Combining LinkedIn post CSV files...")
    
    combined_file = combine_csv_files(input_pattern, output_file)
    
    if combined_file:
        print(f"\n🎉 All done! Master CSV available at: {combined_file}")

if __name__ == "__main__":
    main()
