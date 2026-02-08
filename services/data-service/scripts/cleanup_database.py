"""
Database Cleanup Script

Removes inactive stocks from the database to reduce clutter.
Keeps only S&P 500 stocks.
"""
from sqlalchemy import create_engine, text
from src.config import settings

def cleanup_database():
    """Remove inactive stocks and orphaned data"""
    
    engine = create_engine(settings.DATABASE_URL.replace('+asyncpg', ''))
    
    with engine.connect() as conn:
        print("="*80)
        print("DATABASE CLEANUP - Removing Inactive Stocks")
        print("="*80)
        
        # Get counts before cleanup
        result = conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN is_active = true THEN 1 END) as active,
                COUNT(CASE WHEN is_active = false THEN 1 END) as inactive
            FROM stocks
        """))
        
        counts = result.fetchone()
        print(f"\nBEFORE CLEANUP:")
        print(f"  Total stocks: {counts.total}")
        print(f"  Active (S&P 500): {counts.active}")
        print(f"  Inactive: {counts.inactive}")
        
        # Check for data that will be deleted
        print(f"\nChecking for orphaned data...")
        
        # Price data
        result = conn.execute(text("""
            SELECT COUNT(*) FROM price_data
            WHERE stock_id IN (SELECT id FROM stocks WHERE is_active = false)
        """))
        orphaned_price_data = result.fetchone()[0]
        print(f"  Price data rows for inactive stocks: {orphaned_price_data}")
        
        # Indicators
        result = conn.execute(text("""
            SELECT COUNT(*) FROM indicators
            WHERE stock_id IN (SELECT id FROM stocks WHERE is_active = false)
        """))
        orphaned_indicators = result.fetchone()[0]
        print(f"  Indicator rows for inactive stocks: {orphaned_indicators}")
        
        # Alert history
        result = conn.execute(text("""
            SELECT COUNT(*) FROM alert_history
            WHERE stock_id IN (SELECT id FROM stocks WHERE is_active = false)
        """))
        orphaned_alerts = result.fetchone()[0]
        print(f"  Alert history rows for inactive stocks: {orphaned_alerts}")
        
        print("\n" + "="*80)
        print("⚠️  WARNING: This will DELETE:")
        print(f"  - {counts.inactive} inactive stocks")
        print(f"  - {orphaned_price_data} price data rows")
        print(f"  - {orphaned_indicators} indicator rows")
        print(f"  - {orphaned_alerts} alert history rows")
        print("="*80)
        
        # Prompt for confirmation
        response = input("\nType 'DELETE' to confirm cleanup (or anything else to cancel): ")
        
        if response != 'DELETE':
            print("\n❌ Cleanup cancelled.")
            return
        
        print("\n🗑️  Starting cleanup...")
        
        # Delete orphaned data first (respects foreign key constraints)
        print("\n1. Deleting orphaned indicators...")
        result = conn.execute(text("""
            DELETE FROM indicators
            WHERE stock_id IN (SELECT id FROM stocks WHERE is_active = false)
        """))
        conn.commit()
        print(f"   ✅ Deleted {result.rowcount} rows")
        
        print("\n2. Deleting orphaned price data...")
        result = conn.execute(text("""
            DELETE FROM price_data
            WHERE stock_id IN (SELECT id FROM stocks WHERE is_active = false)
        """))
        conn.commit()
        print(f"   ✅ Deleted {result.rowcount} rows")
        
        print("\n3. Deleting orphaned alert history...")
        result = conn.execute(text("""
            DELETE FROM alert_history
            WHERE stock_id IN (SELECT id FROM stocks WHERE is_active = false)
        """))
        conn.commit()
        print(f"   ✅ Deleted {result.rowcount} rows")
        
        print("\n4. Deleting inactive stocks...")
        result = conn.execute(text("""
            DELETE FROM stocks
            WHERE is_active = false
        """))
        conn.commit()
        print(f"   ✅ Deleted {result.rowcount} rows")
        
        # Verify cleanup
        result = conn.execute(text("SELECT COUNT(*) FROM stocks"))
        final_count = result.fetchone()[0]
        
        print("\n" + "="*80)
        print("✅ CLEANUP COMPLETE!")
        print("="*80)
        print(f"Stocks remaining: {final_count} (should be ~502)")
        print()
        
        # Show disk space reclaimed (if supported)
        try:
            conn.execute(text("VACUUM ANALYZE stocks"))
            conn.execute(text("VACUUM ANALYZE price_data"))
            conn.execute(text("VACUUM ANALYZE indicators"))
            print("✅ Database vacuumed and analyzed")
        except:
            pass

if __name__ == "__main__":
    cleanup_database()
