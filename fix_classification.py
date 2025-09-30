#!/usr/bin/env python3
"""
Fix URL classification in September data based on correct logic:
- URLs containing 'linkedin.com/jobs/' -> jobs
- URLs containing 'linkedin.com/posts/' -> posts  
- Everything else -> others
"""

import pandas as pd

# Read the fresh data
print("📖 Reading fresh September data...")
df = pd.read_csv('./storage/production/september_ingestion_20250924_213351.csv')

print(f"Original data: {len(df)} rows")

# Print current classification breakdown
print("\n📊 CURRENT CLASSIFICATION:")
current_class = df['classification'].value_counts()
for cls, count in current_class.items():
    print(f"  • {cls}: {count}")

# Fix classification based on URL patterns
def classify_url(url):
    url = str(url).lower()
    if 'linkedin.com/jobs/' in url:
        return 'job'
    elif 'linkedin.com/posts/' in url:
        return 'post'
    else:
        return 'other'

# Apply correct classification
df['classification'] = df['url'].apply(classify_url)

# Also fix category to match classification
df['category'] = df['classification'].apply(lambda x: 'jobs' if x == 'job' else ('posts' if x == 'post' else 'others'))

print("\n📊 FIXED CLASSIFICATION:")
fixed_class = df['classification'].value_counts()
for cls, count in fixed_class.items():
    print(f"  • {cls}: {count}")

print("\n📊 FIXED CATEGORY:")
fixed_category = df['category'].value_counts()
for cat, count in fixed_category.items():
    print(f"  • {cat}: {count}")

# Save corrected data
output_path = './storage/production/september_ingestion_FIXED_CLASSIFICATION.csv'
df.to_csv(output_path, index=False)

print(f"\n💾 Saved corrected data to: {output_path}")

# Show some examples
print("\n📋 SAMPLE CLASSIFICATIONS:")
print("Jobs:")
job_samples = df[df['classification'] == 'job'][['url', 'company', 'classification', 'category']].head(3)
for _, row in job_samples.iterrows():
    print(f"  • {row['company']}: {row['url'][:60]}... → {row['classification']}")

print("\nPosts:")
post_samples = df[df['classification'] == 'post'][['url', 'company', 'classification', 'category']].head(3)
for _, row in post_samples.iterrows():
    print(f"  • {row['company']}: {row['url'][:60]}... → {row['classification']}")

if len(df[df['classification'] == 'other']) > 0:
    print("\nOthers:")
    other_samples = df[df['classification'] == 'other'][['url', 'company', 'classification', 'category']].head(3)
    for _, row in other_samples.iterrows():
        print(f"  • {row['company']}: {row['url'][:60]}... → {row['classification']}")