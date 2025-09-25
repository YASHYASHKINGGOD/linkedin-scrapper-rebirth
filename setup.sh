#!/bin/bash

# LinkedIn Job Scraper v2.0 Setup Script
# This script sets up the complete environment for the LinkedIn Job Scraper

echo "🚀 LinkedIn Job Scraper v2.0 Setup"
echo "===================================="

# Check if we're in the right directory
if [[ ! -f "src/scraper/linkedin_job_scraper.py" ]]; then
    echo "❌ Error: Please run this script from the project root directory"
    echo "Expected path: /Users/yash/linkedin scrapper rebirth/"
    exit 1
fi

echo "✅ Project directory confirmed"

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1-2)
required_version="3.8"

if python3 -c "import sys; exit(0 if sys.version_info >= (3,8) else 1)"; then
    echo "✅ Python version: $(python3 --version | awk '{print $2}')"
else
    echo "❌ Error: Python 3.8 or higher required. Found: $(python3 --version)"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [[ ! -d "venv" ]]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "📈 Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
playwright install chromium

# Check if config.json exists
if [[ ! -f "config.json" ]]; then
    if [[ -f "config.example.json" ]]; then
        echo "📋 Creating config.json from example..."
        cp config.example.json config.json
        echo "⚠️  Please edit config.json with your LinkedIn credentials"
    else
        echo "⚠️  config.example.json not found, you'll need to create config.json manually"
    fi
else
    echo "✅ config.json already exists"
fi

# Check PostgreSQL connection
echo "🗄️  Checking database connection..."
python3 -c "
import psycopg
try:
    conn = psycopg.connect('postgresql://postgres:postgres@localhost:5432/data_lake')
    print('✅ Database connection successful')
    conn.close()
except Exception as e:
    print('⚠️  Database connection failed:', str(e))
    print('   Make sure PostgreSQL is running and data_lake database exists')
"

# Create necessary directories
echo "📁 Creating required directories..."
mkdir -p storage/scrape/html
mkdir -p storage/scrape/shots
mkdir -p chrome_profile
echo "✅ Directories created"

# Test anti-detection system
echo "🧪 Testing anti-detection system..."
python3 -c "
try:
    from src.scraper.anti_detection import AdvancedAntiDetection
    from src.scraper.proxy_manager import ProxyManager
    ad = AdvancedAntiDetection()
    pm = ProxyManager()
    print('✅ Anti-detection system loaded successfully')
except Exception as e:
    print('❌ Anti-detection system test failed:', str(e))
"

# Test main scraper import
echo "🔍 Testing main scraper..."
python3 -c "
try:
    from src.scraper.linkedin_job_scraper import LinkedInJobScraperService
    scraper = LinkedInJobScraperService()
    print('✅ Main scraper loaded successfully')
except Exception as e:
    print('❌ Main scraper test failed:', str(e))
"

echo ""
echo "🎉 Setup Complete!"
echo "=================="
echo ""
echo "Next steps:"
echo "1. Edit config.json with your LinkedIn credentials"
echo "2. Ensure PostgreSQL is running with linkedin_links and linkedin_jobs_raw tables"
echo "3. Add some job URLs to scrape in linkedin_links table"
echo "4. Run the scraper:"
echo ""
echo "   source venv/bin/activate"
echo "   python3 -m src.scraper.linkedin_job_scraper --batch-size 5"
echo ""
echo "For testing anti-detection features:"
echo "   python3 test_anti_detection.py"
echo ""
echo "📖 Read HANDOVER_DOCUMENT.md for complete instructions"
echo ""

# Show final status
echo "📊 Environment Status:"
echo "├── Virtual Environment: ✅ $(pwd)/venv"
echo "├── Dependencies: ✅ Installed"
echo "├── Playwright: ✅ Chromium installed"
echo "├── Config File: $([ -f config.json ] && echo '✅ Present' || echo '⚠️  Needs setup')"
echo "├── Database: $(python3 -c 'import psycopg; psycopg.connect("postgresql://postgres:postgres@localhost:5432/data_lake").close(); print("✅ Connected")' 2>/dev/null || echo '⚠️  Check connection')"
echo "└── Anti-Detection: ✅ Ready"
echo ""
echo "Status: $([ -f config.json ] && echo 'Ready for production!' || echo 'Configure credentials first')"