#!/usr/bin/env python3
"""
Test Growth Desk parsing logic
"""

# Sample data from debug output
test_data = [
    ['Company', 'Role', 'Location', 'Link', 'CTC', 'Experience', 'JD'],
    ['1st September'],
    ["shoppin'", 'founder's office (2)', 'Delhi', 'https://www.linkedin.com/posts/shlok-bhartiya_were-hiring-2-killers-for-the-founders-activity-7367907541747470338-E2ww?utm_source=share&utm_medium=member_desktop&rcm=ACoAACyt6owBgCJAq-TByNiprZWFxqH4aBa72eo'],
    ['Jupiter', 'Founder's & President's Office', 'Bengaluru', 'https://www.linkedin.com/posts/rkpande_aspirational-activity-7368155092044144640-diyt?utm_source=share&utm_medium=member_desktop&rcm=ACoAACyt6owBgCJAq-TByNiprZWFxqH4aBa72eo', '', '3-5'],
    ['Remoat Teams', 'Growth Chief of Staff', 'Remote', 'https://www.linkedin.com/jobs/view/4293537634'],
]

def get_cell_value(row, col_idx):
    if col_idx < len(row) and row[col_idx]:
        return str(row[col_idx]).strip()
    return ""

def test_parsing():
    current_date = ""
    records = []
    
    for row_idx, row in enumerate(test_data):
        if not row:
            continue
        
        print(f"Processing row {row_idx + 1}: {row}")
        
        # Check for date headers
        if len(row) == 1 and row[0]:
            cell_text = str(row[0]).strip().lower()
            print(f"  Single cell: '{cell_text}'")
            import re
            date_pattern = r'(\d{1,2})(?:st|nd|rd|th)?\s+september'
            match = re.search(date_pattern, cell_text)
            if match:
                day = match.group(1)
                current_date = f"Sep {day}, 2025"
                print(f"  -> Found date: {current_date}")
                continue
            else:
                print(f"  -> No date match for: {cell_text}")
        
        # Check for headers
        row_text = " ".join([str(cell).strip() for cell in row if cell])
        if any(word in row_text.lower() for word in ["company", "role", "location", "link"]):
            print(f"  -> Skipping header row")
            continue
        
        # Extract data
        company = get_cell_value(row, 0)
        role = get_cell_value(row, 1) 
        location = get_cell_value(row, 2)
        url = get_cell_value(row, 3)
        ctc = get_cell_value(row, 4)
        experience = get_cell_value(row, 5)
        
        print(f"  Extracted: company='{company}', role='{role}', location='{location}', url='{url}'")
        
        # Validation checks
        if not url or "linkedin.com" not in url:
            print(f"  -> Skipping: No valid LinkedIn URL")
            continue
            
        if not company or company in ["-", ""]:
            print(f"  -> Skipping: No valid company")
            continue
        
        record_date = current_date if current_date else "Sep 1, 2025"
        
        record = {
            "url": url,
            "company": company,
            "role": role,
            "location": location,
            "experience": experience,
            "ctc": ctc,
            "date_in_source": record_date
        }
        
        records.append(record)
        print(f"  ✅ Added record: {company} - {role}")
    
    print(f"\n📊 Final result: {len(records)} records extracted")
    for i, record in enumerate(records, 1):
        print(f"{i}. {record['company']} - {record['role']} - {record['date_in_source']}")

if __name__ == "__main__":
    test_parsing()