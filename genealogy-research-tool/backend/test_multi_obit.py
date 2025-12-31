import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, ObituaryCache, ExtractedFact
from services.llm_extractor import process_obituary_full
from utils.hash_utils import hash_url
import os

async def main():
    # Connect to actual MariaDB
    DATABASE_URL = (
        f"mysql+pymysql://{os.getenv('MARIADB_USER', 'genealogy')}:"
        f"{os.getenv('MARIADB_PASSWORD')}@"
        f"{os.getenv('MARIADB_HOST', 'mariadb')}:3306/"
        f"{os.getenv('MARIADB_DATABASE', 'genealogy_cache')}"
        f"?charset=utf8mb4"
    )
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    # Load all 3 obituaries
    test_data_dir = Path(__file__).parent / "tests" / "test_data"
    
    obituaries = [
        ("terrence_obit.txt", "http://test.com/terrence"),
        ("maxine_obit.txt", "http://test.com/maxine"),
        ("patricia_obit.txt", "http://test.com/patricia"),
    ]
    
    for filename, url in obituaries:
        with open(test_data_dir / filename) as f:
            text = f.read()
        
        # Check if already processed
        existing = db.query(ObituaryCache).filter(
            ObituaryCache.url_hash == hash_url(url)
        ).first()
        
        if existing:
            print(f"✓ {filename} already processed (id={existing.id})")
            continue
        
        # Create obituary record
        obit = ObituaryCache(
            url=url,
            url_hash=hash_url(url),
            extracted_text=text,
            processing_status='processing'
        )
        db.add(obit)
        db.commit()
        db.refresh(obit)
        
        # Process
        print(f"\n⚙ Processing {filename}...")
        result = await process_obituary_full(db, obit.id, text)
        
        obit.processing_status = 'completed'
        db.commit()
        
        print(f"✓ {result['persons_extracted']} persons, {result['facts_extracted']} facts")
    
    # Now analyze cross-obituary data
    print("\n" + "="*60)
    print("CROSS-OBITUARY ANALYSIS")
    print("="*60)
    
    # Find people mentioned in multiple obituaries
    from sqlalchemy import func, distinct
    
    result = db.query(
        ExtractedFact.subject_name,
        func.count(distinct(ExtractedFact.obituary_cache_id)).label('obit_count')
    ).group_by(
        ExtractedFact.subject_name
    ).having(
        func.count(distinct(ExtractedFact.obituary_cache_id)) > 1
    ).order_by(
        func.count(distinct(ExtractedFact.obituary_cache_id)).desc()
    ).all()
    
    print(f"\nPeople mentioned in multiple obituaries:")
    for name, count in result:
        print(f"  {name}: {count} obituaries")
        
        # Show which obituaries
        facts = db.query(ExtractedFact).filter(
            ExtractedFact.subject_name == name
        ).all()
        
        obit_ids = set(f.obituary_cache_id for f in facts)
        obits = db.query(ObituaryCache).filter(
            ObituaryCache.id.in_(obit_ids)
        ).all()
        
        for obit in obits:
            url_short = obit.url.split('/')[-1]
            print(f"    - {url_short}")
    
    # Name variants to detect
    print(f"\n\nName variants that need fuzzy matching:")
    
    # Get all unique names
    all_names = db.query(distinct(ExtractedFact.subject_name)).all()
    all_names = [n[0] for n in all_names]
    
    # Simple detection of likely variants
    from collections import defaultdict
    surname_groups = defaultdict(list)
    
    for name in all_names:
        parts = name.split()
        if len(parts) >= 2:
            surname = parts[-1]
            surname_groups[surname].append(name)
    
    for surname, names in surname_groups.items():
        if len(names) > 1:
            # Check for potential variants
            first_names = [' '.join(n.split()[:-1]) for n in names]
            unique_firsts = set(first_names)
            if len(unique_firsts) > 1:
                print(f"\n  {surname} family:")
                for name in names:
                    print(f"    - {name}")
    
    db.close()

if __name__ == "__main__":
    asyncio.run(main())
