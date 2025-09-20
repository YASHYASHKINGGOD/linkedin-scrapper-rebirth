# LinkedIn Pipeline Testing

## Testing Strategy: Real Data First

This testing setup prioritizes **real data testing** over extensive mocking for faster development and more reliable validation.

## Test Categories

### 1. Unit Tests (`tests/unit/`)
- Test configuration parsing and validation
- Test message schema validation  
- Test utility functions
- **No external dependencies** - safe to run anywhere

### 2. Component Tests (`tests/components/`)
- Test individual pipeline components with real data when available
- Skip gracefully if credentials not present
- Fast validation of real Google Sheets access and data structure

### 3. Live Tests (`tests/live/`)
- Full integration with real Google Sheets, database, and services
- Requires `LIVE_TESTS=1` environment variable to enable
- Tests actual ingestion, import, classification, and routing

### 4. Integration Tests (`tests/integration/`)
- Test task chains and component interactions
- May use mocking for external services

## Quick Start

```bash
# 1. Run smoke test to verify setup
make test.smoke

# 2. Run unit tests (safe, no external dependencies)
make test.unit

# 3. Run component tests (uses real data if credentials available)
make test.components  

# 4. Run live tests (requires LIVE_TESTS=1)
make test.live

# 5. End-to-end pipeline test
make test.e2e
```

## Configuration

### Google Sheets Setup
Your real Google Sheets URLs are configured in:
- `config/sheets.yaml` - Contains the 3 LinkedIn data sheets
- `.env` - Points to OAuth credentials and config files

### Credentials Required
- `client_secret_*.json` - Google OAuth client (present)
- `config.json` - LinkedIn credentials (present)
- `google_token.json` - Created on first OAuth run

### Database Setup
- Tests use your existing `data_lake` database
- Tables: `linkedin_links`, `linkedin_posts_raw`, `linkedin_jobs_raw`

## Real Google Sheets

The tests use these actual sheets:
1. `1p7O7tUBYM94IqEmIlXp8a5B0nGdX8DwP-bmVFu0FAK0` (Sheet 1)
2. `14OmQuYyreTa_ehui2vGXbydNpMsJCrCTArolMozuPG0` (Sheet 2) 
3. `1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q` (Sheet 3)

## Benefits of Real Data Testing

✅ **Faster Development**: No complex mocking infrastructure  
✅ **Real Validation**: Tests actual Google Sheets access and data formats  
✅ **True Integration**: End-to-end validation with actual services  
✅ **Immediate Feedback**: Catches real-world issues quickly  
✅ **Simpler Maintenance**: Less mock setup and synchronization  

## Test Execution Flow

1. **Smoke Test** (`python test_smoke.py`)
   - Verifies all files and credentials present
   - Tests basic Google Sheets access
   - Checks database and Redis connectivity

2. **Unit Tests** (`make test.unit`)
   - Configuration parsing
   - Message schema validation
   - No external calls

3. **Component Tests** (`make test.components`)
   - Real Google Sheets ingestion
   - CSV generation and validation
   - Skips if credentials missing

4. **Live Tests** (`LIVE_TESTS=1 make test.live`)
   - Full ingestion → import → classify chain
   - Real database operations
   - Actual LinkedIn URL processing

5. **E2E Test** (`make test.e2e`)
   - Complete pipeline with real data
   - Requires running Celery worker
   - Tests task routing and execution

## Troubleshooting

**Google Sheets Access Issues**:
- Check OAuth token: `ls -la google_token.json`
- Re-authenticate: `rm google_token.json` and run test
- Verify sheet sharing permissions

**Database Issues**:
- Check connection: `psql $DATABASE_URL -c "SELECT 1"`
- Verify tables exist: Check existing tables as per rules

**Redis Issues**:
- Check Redis running: `brew services list | grep redis`
- Test connection: `redis-cli ping`

This approach gets you testing with real data immediately, catching integration issues early while keeping the test suite maintainable! 🧪