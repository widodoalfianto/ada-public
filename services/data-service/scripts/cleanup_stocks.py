
import asyncio
import argparse
import sys
import os
from sqlalchemy import text, select

# Add parent dir to path to import src
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database import init_db, AsyncSessionLocal
from src.consts import INITIAL_STOCKS
from src.models import Stock

async def cleanup_stocks(dry_run: bool = False, keep_only_initial: bool = True):
    print("🧹 Starting Database Cleanup...")
    await init_db()
    
    async with AsyncSessionLocal() as session:
        # 1. Get All Stocks
        print("Fetching existing stocks...")
        result = await session.execute(select(Stock))
        all_stocks = result.scalars().all()
        
        existing_map = {s.symbol: s.id for s in all_stocks}
        print(f"Found {len(existing_map)} stocks in DB.")
        
        # 2. Determine Keep Set
        keep_symbols = set(INITIAL_STOCKS)
        
        # 3. Identify Removals
        to_delete = []
        for symbol, stock_id in existing_map.items():
            if keep_only_initial:
                if symbol not in keep_symbols:
                    to_delete.append((symbol, stock_id))
        
        if not to_delete:
            print("✨ Database is clean! No stocks to remove.")
            return

        print(f"⚠️  Found {len(to_delete)} stocks to REMOVE.")
        if len(to_delete) <= 20:
            print(f"To Remove: {[s[0] for s in to_delete]}")
        else:
            print(f"To Remove (First 20): {[s[0] for s in to_delete[:20]]} ...")
            
        if dry_run:
            print("🚫 DRY RUN: No changes made.")
            return
            
        # 4. Perform Deletion
        print("🔥 Deleting...")
        ids_to_remove = [s[1] for s in to_delete]
        
        if not ids_to_remove:
            return

        # Delete related data first (Manual Cascade)
        # Using chunks to avoid "too many parameters" if list is huge (17,000)
        chunk_size = 1000
        for i in range(0, len(ids_to_remove), chunk_size):
            chunk = ids_to_remove[i:i+chunk_size]
            
            # Using raw SQL with tuple param is tricky with SQLAlchemy async, 
            # simplest is to delete where id = any(:ids)
            
            # Indicators
            await session.execute(text("DELETE FROM indicators WHERE stock_id = ANY(:ids)"), {"ids": chunk})
            # Price Data
            await session.execute(text("DELETE FROM price_data WHERE stock_id = ANY(:ids)"), {"ids": chunk})
            # Alert History
            await session.execute(text("DELETE FROM alert_history WHERE stock_id = ANY(:ids)"), {"ids": chunk})
            # Fetch Failures
            await session.execute(text("DELETE FROM fetch_failures WHERE stock_id = ANY(:ids)"), {"ids": chunk})
            # Finally, Stocks
            await session.execute(text("DELETE FROM stocks WHERE id = ANY(:ids)"), {"ids": chunk})
            
            await session.commit()
            print(f"Processed chunk {i//chunk_size + 1}/{len(ids_to_remove)//chunk_size + 1}")
            
        print("✅ Cleanup Complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Cleanup inactive/unwanted stocks.')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without doing it.')
    parser.add_argument('--keep-only-initial', action='store_true', default=True, help='Delete anything NOT in INITIAL_STOCKS (Default: True).')
    
    args = parser.parse_args()
    
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(cleanup_stocks(dry_run=args.dry_run, keep_only_initial=args.keep_only_initial))
