#!/usr/bin/env python3
"""
Test script for fact-based extraction.
Run from the backend directory: python tests/test_fact_extraction.py
"""

import sys
import os
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import get_db, ObituaryCache, ExtractedFact
from models.database import SessionLocal
from services.llm_extractor import extract_facts_from_obituary
from utils.hash_utils import hash_url, hash_content

# Test obituary from Obit-parsing.md
TEST_OBITUARY = """
Kaczmarowski, Terrence E. Thursday, December 18, 2008, age 80 years.
Beloved husband of Maxine (nee Paradowski). Loving father of the late
Patricia (Steve) Blundon. Cherished grandfather of Ryan (Amy) and Megan
(Ross) Wurz. Proud gramps of Autumn and Caralyn. Brother-in-law of
Reginald (Donna) Paradowski and Joseph (Rose Mary) Paradowski.
"""


async def test_extraction():
    """Test fact extraction from sample obituary."""
    print("=" * 60)
    print("FACT-BASED EXTRACTION TEST")
    print("=" * 60)

    db = SessionLocal()

    try:
        # Create test obituary record
        test_url = "http://test.example.com/obituary/kaczmarowski"
        url_hash = hash_url(test_url)

        # Check if already exists
        existing = db.query(ObituaryCache).filter(
            ObituaryCache.url_hash == url_hash
        ).first()

        if existing:
            print(f"Using existing obituary record (id={existing.id})")
            obituary = existing

            # Delete any existing facts for clean test
            deleted = db.query(ExtractedFact).filter(
                ExtractedFact.obituary_cache_id == obituary.id
            ).delete()
            db.commit()
            print(f"Deleted {deleted} existing facts for clean test")
        else:
            # Create new obituary record
            obituary = ObituaryCache(
                url=test_url,
                url_hash=url_hash,
                content_hash=hash_content(TEST_OBITUARY),
                extracted_text=TEST_OBITUARY,
                processing_status='processing'
            )
            db.add(obituary)
            db.commit()
            db.refresh(obituary)
            print(f"Created new obituary record (id={obituary.id})")

        print("\nInput Obituary:")
        print("-" * 40)
        print(TEST_OBITUARY.strip())
        print("-" * 40)

        # Extract facts
        print("\nExtracting facts with LLM...")
        facts = await extract_facts_from_obituary(
            db=db,
            obituary_cache_id=obituary.id,
            obituary_text=TEST_OBITUARY
        )

        # Update obituary status
        obituary.processing_status = 'completed'
        db.commit()

        print(f"\nExtracted {len(facts)} facts:")
        print("=" * 60)

        # Group by subject for display
        subjects = {}
        for fact in facts:
            if fact.subject_name not in subjects:
                subjects[fact.subject_name] = []
            subjects[fact.subject_name].append(fact)

        for subject_name, subject_facts in subjects.items():
            print(f"\n{subject_name} ({subject_facts[0].subject_role}):")
            for fact in subject_facts:
                inferred = " [INFERRED]" if fact.is_inferred else ""
                print(f"  [{fact.confidence_score:.2f}] {fact.fact_type}: {fact.fact_value}{inferred}")
                if fact.related_name:
                    print(f"         -> Related to: {fact.related_name} ({fact.relationship_type})")
                if fact.is_inferred and fact.inference_basis:
                    print(f"         Basis: {fact.inference_basis}")

        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)

        return facts

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_extraction())
