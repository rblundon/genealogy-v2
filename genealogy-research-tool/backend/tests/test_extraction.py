import pytest
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, ObituaryCache
from services.llm_extractor import process_obituary_full
from utils.hash_utils import hash_url


@pytest.fixture
def db_session():
    """Create test database session"""
    # Use SQLite for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.mark.asyncio
async def test_patricia_extraction(db_session):
    """Test extraction from Patricia's obituary"""

    # Load test data
    test_data_dir = Path(__file__).parent / "test_data"
    with open(test_data_dir / "patricia_obit.txt") as f:
        obit_text = f.read()

    # Create obituary record
    obit = ObituaryCache(
        url="http://test.com/patricia",
        url_hash=hash_url("http://test.com/patricia"),
        extracted_text=obit_text,
        processing_status='processing'
    )
    db_session.add(obit)
    db_session.commit()
    db_session.refresh(obit)

    # Run extraction
    result = await process_obituary_full(db_session, obit.id, obit_text)

    # Verify results
    print(f"\nExtracted {result['persons_extracted']} persons")
    print(f"Extracted {result['facts_extracted']} facts")

    # Check key persons were identified
    person_names = [p['full_name'] for p in result['persons']]
    assert any('Patricia' in name for name in person_names), "Patricia not found"
    assert any('Steven' in name for name in person_names), "Steven not found"
    assert any('Ryan' in name for name in person_names), "Ryan not found"
    assert any('Amy' in name for name in person_names), "Amy not found"
    assert any('Megan' in name for name in person_names), "Megan not found"
    assert any('Ross' in name for name in person_names), "Ross not found"

    # Check key facts
    fact_types = [f['fact_type'] for f in result['facts']]
    assert 'person_death_date' in fact_types, "Death date not extracted"
    assert 'person_death_age' in fact_types, "Death age not extracted"
    assert 'maiden_name' in fact_types, "Maiden name not extracted"
    assert 'marriage_duration' in fact_types, "Marriage duration not extracted"

    # Print summary
    print("\nPersons extracted:")
    for p in result['persons']:
        print(f"  - {p['full_name']} ({p['role']})")
        if p.get('maiden_name'):
            print(f"    Maiden: {p['maiden_name']}")
        if p.get('nickname'):
            print(f"    Nickname: {p['nickname']}")

    print("\nKey facts:")
    for f in result['facts'][:10]:
        print(f"  [{f['confidence_score']}] {f['fact_type']}: {f['subject_name']} -> {f['fact_value']}")


@pytest.mark.asyncio
async def test_terrence_extraction(db_session):
    """Test extraction from Terrence's obituary"""

    # Load test data
    test_data_dir = Path(__file__).parent / "test_data"
    with open(test_data_dir / "terrence_obit.txt") as f:
        obit_text = f.read()

    # Create obituary record
    obit = ObituaryCache(
        url="http://test.com/terrence",
        url_hash=hash_url("http://test.com/terrence"),
        extracted_text=obit_text,
        processing_status='processing'
    )
    db_session.add(obit)
    db_session.commit()
    db_session.refresh(obit)

    # Run extraction
    result = await process_obituary_full(db_session, obit.id, obit_text)

    print(f"\nExtracted {result['persons_extracted']} persons")
    print(f"Extracted {result['facts_extracted']} facts")

    # Check key persons
    person_names = [p['full_name'] for p in result['persons']]
    assert any('Terrence' in name for name in person_names), "Terrence not found"
    assert any('Maxine' in name for name in person_names), "Maxine not found"
    assert any('Patricia' in name for name in person_names), "Patricia not found"

    # Check "the late" is detected
    for p in result['persons']:
        if 'Patricia' in p.get('full_name', ''):
            assert p.get('is_deceased', False), "Patricia should be marked as deceased (the late)"

    print("\nPersons extracted:")
    for p in result['persons']:
        deceased_marker = " [DECEASED]" if p.get('is_deceased') else ""
        print(f"  - {p['full_name']} ({p['role']}){deceased_marker}")


@pytest.mark.asyncio
async def test_maxine_extraction(db_session):
    """Test extraction from Maxine's obituary"""

    # Load test data
    test_data_dir = Path(__file__).parent / "test_data"
    with open(test_data_dir / "maxine_obit.txt") as f:
        obit_text = f.read()

    # Create obituary record
    obit = ObituaryCache(
        url="http://test.com/maxine",
        url_hash=hash_url("http://test.com/maxine"),
        extracted_text=obit_text,
        processing_status='processing'
    )
    db_session.add(obit)
    db_session.commit()
    db_session.refresh(obit)

    # Run extraction
    result = await process_obituary_full(db_session, obit.id, obit_text)

    print(f"\nExtracted {result['persons_extracted']} persons")
    print(f"Extracted {result['facts_extracted']} facts")

    # Check key persons
    person_names = [p['full_name'] for p in result['persons']]
    assert any('Maxine' in name for name in person_names), "Maxine not found"
    assert any('Terrence' in name for name in person_names), "Terrence not found"
    assert any('Finley' in name for name in person_names), "Finley not found (great-grandchild)"

    # Check maiden name extraction
    for p in result['persons']:
        if 'Maxine' in p.get('full_name', ''):
            assert p.get('maiden_name') == 'Paradowski', f"Maxine's maiden name should be Paradowski, got {p.get('maiden_name')}"

    print("\nPersons extracted:")
    for p in result['persons']:
        print(f"  - {p['full_name']} ({p['role']})")
        if p.get('maiden_name'):
            print(f"    Maiden: {p['maiden_name']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
