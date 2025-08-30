import pandas as pd
import json
from datetime import datetime

def clean_duplicate_names(name):
    """Clean duplicate names like 'Aarti SharmaAarti Sharma' -> 'Aarti Sharma'"""
    if not name or pd.isna(name):
        return name
    
    import re
    name_str = str(name).strip()
    
    # Pattern to match repeated sequences
    match = re.match(r'^(.+?)\1$', name_str)
    if match:
        return match.group(1).strip()
    
    return name_str

# Read the raw CSV file with comments
df = pd.read_csv('outputs/linkedin_batch_posts_20250828_164620.csv')

# Extract comments data
comments_export = {
    "extraction_date": datetime.now().isoformat(),
    "total_posts": len(df),
    "posts_with_comments": int((df['comments_count'] > 0).sum()),
    "total_comments_extracted": int(df['comments_count'].sum()),
    "posts": []
}

for idx, row in df.iterrows():
    # Clean author name
    author_clean = clean_duplicate_names(row['author_name'])
    
    post_data = {
        "post_id": idx + 1,
        "author": author_clean,
        "post_date": row['post_date'],
        "comments_count": int(row['comments_count']),
        "comments": []
    }
    
    # Parse comments JSON if available
    if row['comments_count'] > 0 and row['comments_data_json']:
        try:
            comments_raw = json.loads(row['comments_data_json'])
            for comment in comments_raw:
                clean_comment = {
                    "commentor_name": clean_duplicate_names(comment.get('commentor_name', '')),
                    "commentor_title": comment.get('commentor_title', ''),
                    "comment_text": comment.get('comment_text', '').strip() if comment.get('comment_text') else '',
                    "comment_date": comment.get('comment_date', ''),
                    "comment_likes": comment.get('comment_likes', '')
                }
                post_data["comments"].append(clean_comment)
        except json.JSONDecodeError:
            print(f"Error parsing comments for post {idx + 1}")
    
    comments_export["posts"].append(post_data)

# Save to JSON file
json_filename = 'outputs/linkedin_comments_extracted.json'
with open(json_filename, 'w', encoding='utf-8') as f:
    json.dump(comments_export, f, indent=2, ensure_ascii=False)

print("📄 LINKEDIN COMMENTS EXTRACTION COMPLETE")
print("="*50)
print(f"✅ JSON file saved: {json_filename}")
print(f"📊 Total posts: {comments_export['total_posts']}")
print(f"💬 Posts with comments: {comments_export['posts_with_comments']}")
print(f"📝 Total comments: {comments_export['total_comments_extracted']}")

# Display sample comments
print("\n🔍 SAMPLE COMMENTS:")
print("-"*30)
for post in comments_export["posts"]:
    if post["comments_count"] > 0:
        print(f"\n📌 {post['author']} (Post {post['post_id']}):")
        for i, comment in enumerate(post["comments"][:3], 1):  # Show max 3 comments per post
            print(f"  {i}. {comment['commentor_name']}")
            if comment['comment_text']:
                print(f"     💭 {comment['comment_text'][:100]}{'...' if len(comment['comment_text']) > 100 else ''}")
            print(f"     ⏰ {comment['comment_date']}")
        if len(post["comments"]) > 3:
            print(f"     ... and {len(post['comments']) - 3} more")

print(f"\n🎯 READY FOR USE!")
print(f"The comments are now available in clean JSON format at: {json_filename}")
