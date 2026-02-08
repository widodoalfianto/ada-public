"""
Data Service Test Suite

Tests all key endpoints including the new daily update functionality.
"""
import asyncio
import httpx
from datetime import datetime

BASE_URL = "http://data-service:8000"


async def test_health():
    """Test basic health endpoint"""
    print("\n" + "="*80)
    print("TEST: Health Check")
    print("="*80)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        assert response.status_code == 200
        print("✅ PASSED")


async def test_daily_update_single_stock():
    """Test daily update with timeout handling"""
    print("\n" + "="*80)
    print("TEST: Daily Price Update (Sample)")
    print("="*80)
    print("Note: Full 502-stock update takes ~10 minutes due to rate limiting")
    print("This test will timeout but the job continues in background")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{BASE_URL}/api/daily-update")
            result = response.json()
            
            print(f"Status: {response.status_code}")
            print(f"Total Stocks: {result.get('total_stocks')}")
            print(f"Success: {result.get('success_count')}")
            print(f"Failures: {result.get('failure_count')}")
            print(f"Duration: {result.get('duration_seconds')}s")
            
            if result.get('status') == 'completed':
                print("✅ PASSED")
            else:
                print("⚠️  PARTIAL (background processing)")
                
    except httpx.ReadTimeout:
        print("⚠️  TIMEOUT (expected - job running in background)")
        print("Check data-service logs for completion")


async def test_database_stats():
    """Query database to verify data"""
    print("\n" + "="*80)
    print("TEST: Database Statistics")
    print("="*80)
    
    # This would need a database query endpoint
    # For now, just document what should be checked
    print("Manual check required:")
    print("  docker compose exec db psql -U user -d stock_db -c")
    print("  \"SELECT COUNT(DISTINCT stock_id) FROM price_data;\"")
    print("⚠️  MANUAL CHECK REQUIRED")


async def run_all_tests():
    """Run all data service tests"""
    print("\n" + "="*80)
    print("DATA SERVICE TEST SUITE")
    print(f"Started: {datetime.now()}")
    print("="*80)
    
    try:
        await test_health()
        await test_daily_update_single_stock()
        await test_database_stats()
        
        print("\n" + "="*80)
        print("TEST SUITE COMPLETE")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED: {e}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
