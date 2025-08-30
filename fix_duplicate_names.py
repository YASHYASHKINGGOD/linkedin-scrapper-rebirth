import pandas as pd
import re

def clean_duplicate_names(name):
    """Clean duplicate names like 'Aarti SharmaAarti Sharma' -> 'Aarti Sharma'"""
    if not name or pd.isna(name):
        return name
    
    name_str = str(name).strip()
    
    # Pattern 1: Check if string is repeated exactly (e.g., "Aarti SharmaAarti Sharma")
    # Try to find if the name is repeated without spaces between
    # First, let's see if we can split at capital letters to find the pattern
    
    # Look for patterns like "FirstnameLastnameFirstnameLastname"
    # Use regex to find repeated patterns
    import re
    
    # Pattern to match repeated sequences
    # This will match "Aarti SharmaAarti Sharma" -> "Aarti Sharma"
    match = re.match(r'^(.+?)\1$', name_str)
    if match:
        return match.group(1).strip()
    
    # Alternative approach: look for capital letter patterns
    # Split by capital letters to identify name components
    parts = re.findall(r'[A-Z][a-z]*', name_str)
    if len(parts) >= 4:
        # Check if first half matches second half
        mid = len(parts) // 2
        first_half = parts[:mid]
        second_half = parts[mid:mid*2]  # Only check same length
        
        if len(first_half) == len(second_half) and first_half == second_half:
            return ' '.join(first_half)
    
    # Split into words and check traditional way
    words = name_str.split()
    
    # Check if we have exactly 4 words and first 2 match last 2
    if len(words) == 4 and words[0] == words[2] and words[1] == words[3]:
        return f"{words[0]} {words[1]}"
    
    # Check if we have even number of words and first half matches second half
    if len(words) >= 4 and len(words) % 2 == 0:
        mid = len(words) // 2
        first_half = ' '.join(words[:mid])
        second_half = ' '.join(words[mid:])
        if first_half == second_half:
            return first_half
    
    return name_str

# Read the CSV file with the successful extractions
df = pd.read_csv('outputs/linkedin_batch_posts_20250828_160227.csv')

print("Before cleaning:")
print("Author names:", df['author_name'].tolist())

# Clean the author names
df['author_name'] = df['author_name'].apply(clean_duplicate_names)

print("\nAfter cleaning:")
print("Author names:", df['author_name'].tolist())

# Save the cleaned CSV
output_file = 'outputs/linkedin_batch_posts_CLEANED.csv'
df.to_csv(output_file, index=False)

print(f"\n✅ Cleaned CSV saved as: {output_file}")

# Display summary
print(f"\n📊 Summary:")
print(f"Total posts: {len(df)}")
print(f"Successful extractions: {sum(df['extraction_success'])}")
print(f"Posts with author names: {sum(df['author_name'] != '')}")
print(f"Posts with content: {sum(df['post_text'].str.len() > 0)}")
