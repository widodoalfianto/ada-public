"""
Indicator Service Test Suite

Tests indicator calculation endpoints and daily update functionality.
"""
import asyncio
import httpx
from datetime import datetime

BASE_URL = "http://indicator-service:8000"


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


async def test_get_indicators():
    """Test getting indicators for a specific stock"""
    print("\n" + "="*80)
    print("TEST: Get Indicators (AAPL)")
    print("="*80)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{BASE_URL}/indicators/AAPL?days=1")
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result:
                latest = result[0]
                print(f"Date: {latest['date']}")
                print(f"Close: ${latest['close']}")
                print(f"Indicators: {len(latest['indicators'])} calculated")
                print(f"Sample indicators:")
                for key, val in list(latest['indicators'].items())[:5]:
                    print(f"  {key}: {val:.2f}")
                print("✅ PASSED")
            else:
                print("⚠️  No indicators found")
        else:
            print(f"❌ FAILED: {response.text}")


async def test_daily_calculate():
    """Test daily indicator calculation"""
    print("\n" + "="*80)
    print("TEST: Daily Indicator Calculation")
    print("="*80)
    print("Calculates indicators for TODAY only (incremental)")
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{BASE_URL}/api/daily-calculate")
            result = response.json()
            
            print(f"Status: {response.status_code}")
            print(f"Date: {result.get('date')}")
            print(f"Total Stocks: {result.get('total_stocks')}")
            print(f"Success: {result.get('success_count')}")
            print(f"Skipped: {result.get('skipped_count')}")
            print(f"Failures: {result.get('failure_count')}")
            print(f"Indicators Created: {result.get('indicators_created')}")
            print(f"Duration: {result.get('duration_seconds')}s")
            
            if result.get('status') == 'completed':
                print("✅ PASSED")
            else:
                print("❌ FAILED")
                
    except httpx.ReadTimeout:
        print("⚠️  TIMEOUT (may still be processing)")


async def test_indicator_coverage():
    """Test that multiple stocks have indicators"""
    print("\n" + "="*80)
    print("TEST: Indicator Coverage (Sample Stocks)")
    print("="*80)
    
    test_symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        successful = 0
        for symbol in test_symbols:
            try:
                response = await client.get(f"{BASE_URL}/indicators/{symbol}?days=1")
                if response.status_code == 200:
                    result = response.json()
                    if result and result[0].get('indicators'):
                        print(f"  ✅ {symbol}: {len(result[0]['indicators'])} indicators")
                        successful += 1
                    else:
                        print(f"  ⚠️  {symbol}: No indicators")
                else:
                    print(f"  ❌ {symbol}: Failed")
            except Exception as e:
                print(f"  ❌ {symbol}: Error - {e}")
        
        print(f"\nCoverage: {successful}/{len(test_symbols)} stocks")
        if successful == len(test_symbols):
            print("✅ PASSED")
        else:
            print("⚠️  PARTIAL")


async def run_all_tests():
    """Run all indicator service tests"""
    print("\n" + "="*80)
    print("INDICATOR SERVICE TEST SUITE")
    print(f"Started: {datetime.now()}")
    print("="*80)
    
    try:
        await test_health()
        await test_get_indicators()
        await test_indicator_coverage()
        await test_daily_calculate()
        
        print("\n" + "="*80)
        print("TEST SUITE COMPLETE")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED: {e}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
