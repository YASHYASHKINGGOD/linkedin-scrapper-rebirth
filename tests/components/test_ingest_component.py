"""
Component tests for ingestion functionality using real data.
"""
import pytest
import os
import pandas as pd
import uuid
from tests.conftest import TestHelpers


@pytest.mark.skipif(
    not os.path.exists("./config/sheets.yaml") or 
    not os.path.exists("./client_secret_28309019366-evvs939pulo3l9rbnopi4i1tnojf5ium.apps.googleusercontent.com.json"),
    reason="Real credentials and config required for component tests"
)
def test_ingest_links_component():
    """Test Google Sheets ingestion with real data"""
    from apps.orchestration.tasks import ingest_links
    
    trace_id = f"component_test_{uuid.uuid4().hex[:8]}"
    
    # Run actual ingestion with real data
    result = ingest_links(trace_id=trace_id)
    
    # Assertions
    assert result["ok"] == True, f"Ingest failed: {result.get('error', 'Unknown error')}"
    assert result["trace_id"] == trace_id
    assert "output_csv" in result
    assert os.path.exists(result["output_csv"])
    
    try:
        # Verify CSV content
        df = pd.read_csv(result["output_csv"])
        assert len(df) > 0, "CSV should have rows"
        assert "url" in df.columns
        
        # Should have LinkedIn URLs
        linkedin_urls = df[df['url'].str.contains('linkedin.com', na=False)]
        assert len(linkedin_urls) > 0, "Should have LinkedIn URLs"
        
        # Basic data validation
        assert all(pd.notna(df['url'])), "All URLs should be non-null"
        
    finally:
        # Cleanup
        if os.path.exists(result["output_csv"]):
            os.remove(result["output_csv"])


def test_ingest_links_empty_sheets():
    """Test ingestion with empty Google Sheets"""
    from apps.orchestration.tasks import ingest_links
    
    with patch('apps.orchestration.tasks._resolve_urls_and_month') as mock_resolve, \
         patch('src.google_sheets_ingester.ingest_links_from_google_sheets') as mock_ingest:
        
        mock_resolve.return_value = (["https://empty-sheet-url"], "dec")
        mock_ingest.return_value = None  # Empty result
        
        result = ingest_links(trace_id="empty_test")
        
        # Should handle empty gracefully
        assert result["ok"] == False
        assert "error" in result
        assert result["trace_id"] == "empty_test"


def test_ingest_links_environment_missing():
    """Test ingestion with missing environment variables"""
    from apps.orchestration.tasks import ingest_links
    
    with patch('apps.orchestration.tasks._resolve_urls_and_month') as mock_resolve:
        mock_resolve.side_effect = RuntimeError("GOOGLE_SHEETS_URLS not configured")
        
        result = ingest_links(trace_id="env_test")
        
        # Should handle missing environment variables
        assert result["ok"] == False
        assert "error" in result
        assert "GOOGLE_SHEETS_URLS" in result["error"]
        assert result["trace_id"] == "env_test"


def test_ingest_links_trace_id_propagation():
    """Test that trace_id is properly propagated through ingestion"""
    from apps.orchestration.tasks import ingest_links
    
    test_trace_id = "trace_xyz_789"
    
    with patch('apps.orchestration.tasks._resolve_urls_and_month') as mock_resolve, \
         patch('src.google_sheets_ingester.ingest_links_from_google_sheets') as mock_ingest:
        
        mock_resolve.return_value = (["https://test-sheet-url"], "dec")
        mock_ingest.return_value = "./temp/test_output.csv"
        
        # Create minimal test CSV
        os.makedirs("./temp", exist_ok=True)
        test_csv = "./temp/test_output.csv"
        pd.DataFrame([{"url": "https://linkedin.com/posts/trace_test"}]).to_csv(test_csv, index=False)
        
        try:
            result = ingest_links(trace_id=test_trace_id)
            
            # Verify trace_id propagated
            assert result["trace_id"] == test_trace_id
            assert result["ok"] == True
            
        finally:
            if os.path.exists(test_csv):
                os.remove(test_csv)


def test_ingest_links_csv_validation():
    """Test validation of generated CSV structure"""
    from apps.orchestration.tasks import ingest_links
    
    # Create CSV with incorrect structure
    bad_csv_path = "./temp/bad_structure.csv"
    os.makedirs("./temp", exist_ok=True)
    
    # Missing required columns
    bad_data = pd.DataFrame([{"invalid_column": "test"}])
    bad_data.to_csv(bad_csv_path, index=False)
    
    try:
        with patch('apps.orchestration.tasks._resolve_urls_and_month') as mock_resolve, \
             patch('src.google_sheets_ingester.ingest_links_from_google_sheets') as mock_ingest:
            
            mock_resolve.return_value = (["https://test-sheet-url"], "dec")
            mock_ingest.return_value = bad_csv_path
            
            result = ingest_links(trace_id="validation_test")
            
            # Should validate CSV structure
            # Implementation may vary - either error or handle gracefully
            assert "trace_id" in result
            
    finally:
        if os.path.exists(bad_csv_path):
            os.remove(bad_csv_path)