import pandas as pd
import json
import re

def clean_duplicate_names(name):
    """Clean duplicate names like 'Aarti SharmaAarti Sharma' -> 'Aarti Sharma'"""
    if not name or pd.isna(name):
        return name
    
    name_str = str(name).strip()
    
    # Pattern to match repeated sequences
    # This will match "Aarti SharmaAarti Sharma" -> "Aarti Sharma"
    match = re.match(r'^(.+?)\1$', name_str)
    if match:
        return match.group(1).strip()
    
    # Alternative approach: look for capital letter patterns
    parts = re.findall(r'[A-Z][a-z]*', name_str)
    if len(parts) >= 4:
        # Check if first half matches second half
        mid = len(parts) // 2
        first_half = parts[:mid]
        second_half = parts[mid:mid*2]
        
        if len(first_half) == len(second_half) and first_half == second_half:
            return ' '.join(first_half)
    
    return name_str

def parse_comments_json(comments_json_str):
    """Parse comments JSON string and return formatted summary"""
    if not comments_json_str or comments_json_str == '[]':
        return "No comments"
    
    try:
        comments = json.loads(comments_json_str)
        if not comments:
            return "No comments"
        
        summary = []
        for comment in comments:
            commentor = comment.get('commentor_name', 'Unknown')
            text = comment.get('comment_text', 'No text available')
            date = comment.get('comment_date', '')
            
            # Clean commentor name
            commentor = clean_duplicate_names(commentor)
            
            comment_summary = f"🔸 {commentor}"
            if date:
                comment_summary += f" ({date})"
            if text and text.strip():
                comment_summary += f": {text[:100]}..." if len(text) > 100 else f": {text}"
            
            summary.append(comment_summary)
        
        return "\n".join(summary)
        
    except json.JSONDecodeError:
        return "Error parsing comments"

# Read the CSV file
df = pd.read_csv('outputs/linkedin_batch_posts_20250828_164620.csv')

print("🔧 Processing LinkedIn batch scraper results...")
print(f"📊 Found {len(df)} posts to process")

# Clean author names
print("\n✨ Cleaning author names...")
df['author_name_clean'] = df['author_name'].apply(clean_duplicate_names)

# Parse comments and create readable format
print("💬 Processing comments data...")
df['comments_summary'] = df['comments_data_json'].apply(parse_comments_json)

# Create a summary report
print("\n📋 BATCH SCRAPING SUMMARY REPORT")
print("=" * 50)

for idx, row in df.iterrows():
    post_num = idx + 1
    print(f"\n📌 POST {post_num}:")
    print(f"   👤 Author: {row['author_name_clean']}")
    print(f"   📝 Content: {len(row['post_text'])} characters")
    print(f"   📅 Date: {row['post_date']}")
    print(f"   💬 Comments: {row['comments_count']} found")
    links_count = row['post_links'].count(';') + 1 if (row['post_links'] and not pd.isna(row['post_links'])) else 0
    hashtags_count = row['hashtags'].count(';') + 1 if (row['hashtags'] and not pd.isna(row['hashtags'])) else 0
    print(f"   🔗 Links: {links_count}")
    print(f"   #️⃣ Hashtags: {hashtags_count}")
    
    if row['comments_count'] > 0:
        print(f"   📖 Comment Details:")
        for line in row['comments_summary'].split('\n')[:3]:  # Show first 3 comments
            print(f"      {line}")
        if row['comments_count'] > 3:
            print(f"      ... and {row['comments_count'] - 3} more comments")

# Save cleaned version
output_file = 'outputs/linkedin_batch_posts_FINAL_CLEAN.csv'
df_clean = df[['url', 'author_name_clean', 'post_text', 'post_date', 'comments_count', 'comments_summary', 'post_links', 'hashtags', 'mentions']].copy()
df_clean.columns = ['URL', 'Author', 'Post_Content', 'Date', 'Comments_Count', 'Comments_Details', 'Links', 'Hashtags', 'Mentions']

df_clean.to_csv(output_file, index=False)
print(f"\n✅ Clean results saved to: {output_file}")

# Statistics
total_comments = df['comments_count'].sum()
posts_with_comments = (df['comments_count'] > 0).sum()

print(f"\n📈 FINAL STATISTICS:")
print(f"   📊 Total Posts Processed: {len(df)}")
print(f"   ✅ Successful Extractions: {df['extraction_success'].sum()}")
print(f"   💬 Total Comments Extracted: {total_comments}")
print(f"   📝 Posts with Comments: {posts_with_comments}")
print(f"   📊 Average Comments per Post: {total_comments/len(df):.1f}")

print(f"\n🎉 LinkedIn Batch Scraping Complete!")
