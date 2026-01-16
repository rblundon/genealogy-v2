"""
Unit tests for the rules-based extractor.

Tests each component in isolation and integration tests against ground truth.
"""

import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.rules_extractor import RulesExtractor, extract_facts_with_rules


class TestHeaderParsing:
    """Tests for obituary header parsing."""

    def test_basic_header_with_maiden_name(self):
        """Test parsing header with maiden name in Nee format."""
        text = 'Blundon, Patricia L. "Patsy" (Nee Kaczmarowski) Taken from us too soon on Thursday, August 7, 2008, at the age of 57 years.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        # Find deceased person
        deceased = next((p for p in result['persons'] if p['role'] == 'deceased_primary'), None)

        assert deceased is not None
        assert deceased['surname'] == 'Blundon'
        assert deceased['given_names'] == 'Patricia L.'
        assert deceased['nickname'] == 'Patsy'
        assert deceased['maiden_name'] == 'Kaczmarowski'

    def test_header_without_nickname(self):
        """Test parsing header without nickname."""
        text = 'Kaczmarowski, Terrence E. Thursday, December 18, 2008, age 80 years.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        deceased = next((p for p in result['persons'] if p['role'] == 'deceased_primary'), None)

        assert deceased is not None
        assert deceased['surname'] == 'Kaczmarowski'
        assert deceased['given_names'] == 'Terrence E.'
        assert deceased['nickname'] is None

    def test_header_with_nee_uppercase(self):
        """Test parsing header with NEE in uppercase."""
        text = 'Kaczmarowski, Maxine V. (NEE Paradowski) Reunited with her husband on May 24, 2018 at the age of 87 years.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        deceased = next((p for p in result['persons'] if p['role'] == 'deceased_primary'), None)

        assert deceased is not None
        assert deceased['maiden_name'] == 'Paradowski'


class TestDeathDateExtraction:
    """Tests for death date extraction."""

    def test_death_date_with_day_name(self):
        """Test extracting death date with day name."""
        text = 'Blundon, Patricia L. Taken from us too soon on Thursday, August 7, 2008, at the age of 57 years.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        death_date_facts = [f for f in result['facts'] if f['fact_type'] == 'person_death_date']
        assert len(death_date_facts) == 1
        assert 'August 7, 2008' in death_date_facts[0]['fact_value']

    def test_death_date_simple_format(self):
        """Test extracting death date in simple format."""
        text = 'Kaczmarowski, Maxine V. Reunited on May 24, 2018 at the age of 87 years.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        death_date_facts = [f for f in result['facts'] if f['fact_type'] == 'person_death_date']
        assert len(death_date_facts) == 1
        assert 'May 24, 2018' in death_date_facts[0]['fact_value']


class TestDeathAgeExtraction:
    """Tests for death age extraction."""

    def test_death_age_full_format(self):
        """Test extracting death age with 'at the age of X years'."""
        text = 'Blundon, Patricia L. On Thursday, August 7, 2008, at the age of 57 years.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        death_age_facts = [f for f in result['facts'] if f['fact_type'] == 'person_death_age']
        assert len(death_age_facts) == 1
        assert death_age_facts[0]['fact_value'] == '57'

    def test_death_age_short_format(self):
        """Test extracting death age with 'age X years'."""
        text = 'Kaczmarowski, Terrence E. Thursday, December 18, 2008, age 80 years.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        death_age_facts = [f for f in result['facts'] if f['fact_type'] == 'person_death_age']
        assert len(death_age_facts) == 1
        assert death_age_facts[0]['fact_value'] == '80'


class TestSpouseExtraction:
    """Tests for spouse relationship extraction."""

    def test_wife_of_pattern(self):
        """Test extracting spouse from 'wife of X' pattern."""
        text = 'Blundon, Patricia L. Beloved wife and "Koochie" of Steven, for 38 years.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        # Check marriage fact exists
        marriage_facts = [f for f in result['facts'] if f['fact_type'] == 'marriage']
        assert len(marriage_facts) >= 2  # Bidirectional

        # Check spouse person exists
        spouse = next((p for p in result['persons'] if 'Steven' in p['full_name']), None)
        assert spouse is not None
        assert spouse['role'] == 'spouse'

    def test_husband_of_pattern(self):
        """Test extracting spouse from 'husband of X' pattern."""
        text = 'Kaczmarowski, Terrence E. Beloved husband of Maxine (nee Paradowski).'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        spouse = next((p for p in result['persons'] if 'Maxine' in p['full_name']), None)
        assert spouse is not None
        assert spouse['role'] == 'spouse'

    def test_marriage_duration(self):
        """Test extracting marriage duration."""
        text = 'Blundon, Patricia L. Beloved wife of Steven, for 38 years.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        duration_facts = [f for f in result['facts'] if f['fact_type'] == 'marriage_duration']
        assert len(duration_facts) == 1
        assert '38' in duration_facts[0]['fact_value']


class TestChildrenExtraction:
    """Tests for children extraction."""

    def test_mother_of_with_spouses(self):
        """Test extracting children from 'mother of X (Y)' pattern."""
        text = 'Blundon, Patricia L. Mother of Ryan (Amy) and Megan (Ross) Wurz.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        # Should have Ryan, Amy, Megan, Ross
        persons = {p['full_name']: p for p in result['persons']}

        assert 'Ryan' in str(persons.keys())
        assert 'Amy' in str(persons.keys())
        assert 'Megan' in str(persons.keys())
        assert 'Ross' in str(persons.keys())

        # Megan should have surname Wurz (explicit)
        megan = next((p for p in result['persons'] if 'Megan' in p['full_name']), None)
        assert megan is not None
        assert megan['surname'] == 'Wurz'

    def test_marriage_from_parenthetical(self):
        """Test that parenthetical notation creates marriage facts."""
        text = 'Blundon, Patricia L. Mother of Ryan (Amy) and Megan (Ross) Wurz.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        marriage_facts = [f for f in result['facts'] if f['fact_type'] == 'marriage']

        # Should have marriages for Ryan+Amy and Megan+Ross (bidirectional = 4 facts)
        assert len(marriage_facts) >= 4


class TestParentsExtraction:
    """Tests for parent extraction."""

    def test_daughter_of_pattern(self):
        """Test extracting parents from 'daughter of X and Y' pattern."""
        text = 'Blundon, Patricia L. Dearest daughter of Terrence and Maxine Kaczmarowski.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        parents = [p for p in result['persons'] if p['role'] == 'parent']
        assert len(parents) == 2

        parent_names = [p['full_name'] for p in parents]
        assert 'Terrence Kaczmarowski' in parent_names
        assert 'Maxine Kaczmarowski' in parent_names


class TestGrandchildrenExtraction:
    """Tests for grandchildren extraction."""

    def test_grandma_of_with_ages(self):
        """Test extracting grandchildren with ages."""
        text = 'Blundon, Patricia L. On August 7, 2008. Proud and loving grandma of Autumn (5) and Caralyn (3).'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        grandchildren = [p for p in result['persons'] if p['role'] == 'grandchild']
        assert len(grandchildren) == 2

        # Check birth year approximations
        birth_year_facts = [f for f in result['facts'] if f['fact_type'] == 'person_birth_year_approx']
        assert len(birth_year_facts) == 2

        # Autumn should be ~2003 (2008 - 5)
        autumn_fact = next((f for f in birth_year_facts if 'Autumn' in f['subject_name']), None)
        assert autumn_fact is not None
        assert autumn_fact['fact_value'] == '2003'

    def test_grandchildren_without_ages(self):
        """Test extracting grandchildren without ages."""
        text = 'Kaczmarowski, Terrence E. Cherished grandfather of Ryan (Amy) and Megan (Ross) Wurz.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        # Should find Ryan and Megan with spouses
        persons = [p['full_name'] for p in result['persons']]
        assert any('Ryan' in p for p in persons)
        assert any('Megan' in p for p in persons)


class TestInLawsExtraction:
    """Tests for in-law extraction."""

    def test_sister_in_law_of_pattern(self):
        """Test extracting sister-in-law relationships."""
        text = 'Blundon, Patricia L. Wife of Steven. Sister-in-law of Marty (Katie) Blundon and Monica (Ron) Clasen.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        # Should have Marty, Katie, Monica, Ron
        persons = [p['full_name'] for p in result['persons']]
        assert any('Marty' in p for p in persons)
        assert any('Katie' in p for p in persons)
        assert any('Monica' in p for p in persons)
        assert any('Ron' in p for p in persons)

        # In-law facts should exist
        in_law_facts = [f for f in result['facts'] if f['relationship_type'] and 'in-law' in f['relationship_type']]
        assert len(in_law_facts) >= 2

    def test_brother_in_law_of_pattern(self):
        """Test extracting brother-in-law relationships."""
        text = 'Kaczmarowski, Terrence E. Husband of Maxine. Brother-in-law of Reginald (Donna) Paradowski and Joseph (Rose Mary) Paradowski.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        # Should have Reginald, Donna, Joseph, Rose Mary
        persons = [p['full_name'] for p in result['persons']]
        assert any('Reginald' in p for p in persons)
        assert any('Donna' in p for p in persons)
        assert any('Joseph' in p for p in persons)

    def test_son_in_law_pattern(self):
        """Test extracting son-in-law relationships."""
        text = 'Kaczmarowski, Maxine V. Survived by her faithful son-in-law Steve Blundon.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        steve = next((p for p in result['persons'] if 'Steve' in p['full_name']), None)
        assert steve is not None
        assert steve['role'] == 'in_law'


class TestDeceasedMarkers:
    """Tests for deceased status markers."""

    def test_the_late_pattern(self):
        """Test extracting deceased status from 'the late X' pattern."""
        text = 'Kaczmarowski, Terrence E. Loving father of the late Patricia (Steve) Blundon.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        patricia = next((p for p in result['persons'] if 'Patricia' in p['full_name']), None)
        assert patricia is not None
        assert patricia['is_deceased'] == True

    def test_reunited_with_pattern(self):
        """Test extracting deceased status from 'Reunited with X' pattern."""
        text = 'Kaczmarowski, Maxine V. Reunited with her husband Terrence and daughter Patricia on May 24, 2018.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        # Terrence and Patricia should be marked deceased
        terrence = next((p for p in result['persons'] if 'Terrence' in p['full_name']), None)
        if terrence:
            assert terrence['is_deceased'] == True

        deceased_facts = [f for f in result['facts'] if f['fact_type'] == 'deceased']
        # Should have deceased facts for deceased_primary and reunited persons
        assert len(deceased_facts) >= 1


class TestSurnameInference:
    """Tests for surname inference rules."""

    def test_children_inherit_surname(self):
        """Test that children inherit deceased's surname."""
        text = 'Blundon, Patricia L. Mother of Ryan (Amy).'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        ryan = next((p for p in result['persons'] if 'Ryan' in p['full_name']), None)
        assert ryan is not None
        # Ryan should have inherited Blundon surname or have it inferred
        assert ryan['surname'] == 'Blundon' or ryan['surname_source'] == 'inferred_from_parent'

    def test_spouse_inherits_surname(self):
        """Test that spouse in parentheses inherits surname."""
        text = 'Blundon, Patricia L. Mother of Ryan (Amy) Blundon.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        amy = next((p for p in result['persons'] if 'Amy' in p['full_name']), None)
        assert amy is not None
        # Amy should share Ryan's surname
        assert amy['surname'] == 'Blundon'


class TestSiblingInference:
    """Tests for sibling inference from in-laws."""

    def test_infer_sibling_from_in_law(self):
        """Test inferring sibling relationships from in-laws."""
        text = 'Blundon, Patricia L. Wife of Steven. Sister-in-law of Marty (Katie) Blundon.'

        extractor = RulesExtractor()
        result = extractor.extract_all(text)

        # Marty should be inferred as Steven's sibling
        sibling_facts = [f for f in result['facts']
                       if f['fact_type'] == 'relationship'
                       and f['fact_value'] == 'sibling'
                       and f['is_inferred'] == True]

        # Should have inferred sibling relationship
        assert len(sibling_facts) >= 1


class TestFullObituaryExtraction:
    """Integration tests against full obituary texts."""

    @pytest.fixture
    def patricia_obit(self):
        test_data_dir = Path(__file__).parent / "test_data"
        with open(test_data_dir / "patricia_obit.txt") as f:
            return f.read()

    @pytest.fixture
    def terrence_obit(self):
        test_data_dir = Path(__file__).parent / "test_data"
        with open(test_data_dir / "terrence_obit.txt") as f:
            return f.read()

    @pytest.fixture
    def maxine_obit(self):
        test_data_dir = Path(__file__).parent / "test_data"
        with open(test_data_dir / "maxine_obit.txt") as f:
            return f.read()

    def test_patricia_extraction(self, patricia_obit):
        """Test full extraction from Patricia's obituary."""
        result = extract_facts_with_rules(patricia_obit)

        # Check deceased person
        deceased = next((p for p in result['persons'] if p['role'] == 'deceased_primary'), None)
        assert deceased is not None
        assert deceased['given_names'] == 'Patricia L.'
        assert deceased['surname'] == 'Blundon'
        assert deceased['maiden_name'] == 'Kaczmarowski'
        assert deceased['nickname'] == 'Patsy'

        # Check death facts
        death_date_fact = next((f for f in result['facts'] if f['fact_type'] == 'person_death_date'), None)
        assert death_date_fact is not None
        assert 'August 7, 2008' in death_date_fact['fact_value']

        death_age_fact = next((f for f in result['facts'] if f['fact_type'] == 'person_death_age'), None)
        assert death_age_fact is not None
        assert death_age_fact['fact_value'] == '57'

        # Check key persons exist
        person_names = [p['full_name'] for p in result['persons']]
        assert any('Steven' in p for p in person_names), "Steven not found"
        assert any('Ryan' in p for p in person_names), "Ryan not found"
        assert any('Amy' in p for p in person_names), "Amy not found"
        assert any('Megan' in p for p in person_names), "Megan not found"
        assert any('Ross' in p for p in person_names), "Ross not found"
        assert any('Autumn' in p for p in person_names), "Autumn not found"
        assert any('Caralyn' in p for p in person_names), "Caralyn not found"
        assert any('Terrence' in p for p in person_names), "Terrence not found"
        assert any('Maxine' in p for p in person_names), "Maxine not found"
        assert any('Marty' in p for p in person_names), "Marty not found"
        assert any('Katie' in p for p in person_names), "Katie not found"
        assert any('Monica' in p for p in person_names), "Monica not found"
        assert any('Ron' in p for p in person_names), "Ron not found"

        # Check marriage duration
        duration_fact = next((f for f in result['facts'] if f['fact_type'] == 'marriage_duration'), None)
        assert duration_fact is not None
        assert '38' in duration_fact['fact_value']

        # Count key fact types
        fact_types = [f['fact_type'] for f in result['facts']]
        assert fact_types.count('marriage') >= 8  # Multiple marriages (bidirectional)
        assert fact_types.count('relationship') >= 10  # Multiple relationships

        print(f"\nPatricia extraction: {len(result['persons'])} persons, {len(result['facts'])} facts")

    def test_terrence_extraction(self, terrence_obit):
        """Test full extraction from Terrence's obituary."""
        result = extract_facts_with_rules(terrence_obit)

        # Check deceased person
        deceased = next((p for p in result['persons'] if p['role'] == 'deceased_primary'), None)
        assert deceased is not None
        assert deceased['given_names'] == 'Terrence E.'
        assert deceased['surname'] == 'Kaczmarowski'

        # Check death facts
        death_age_fact = next((f for f in result['facts'] if f['fact_type'] == 'person_death_age'), None)
        assert death_age_fact is not None
        assert death_age_fact['fact_value'] == '80'

        # Check spouse with maiden name
        spouse = next((p for p in result['persons'] if p['role'] == 'spouse'), None)
        assert spouse is not None
        assert 'Maxine' in spouse['full_name']

        # Check "the late" Patricia is marked deceased
        patricia = next((p for p in result['persons'] if 'Patricia' in p['full_name']), None)
        assert patricia is not None
        assert patricia['is_deceased'] == True

        # Check in-laws
        person_names = [p['full_name'] for p in result['persons']]
        assert any('Reginald' in p for p in person_names), "Reginald not found"
        assert any('Joseph' in p for p in person_names), "Joseph not found"

        print(f"\nTerrence extraction: {len(result['persons'])} persons, {len(result['facts'])} facts")

    def test_maxine_extraction(self, maxine_obit):
        """Test full extraction from Maxine's obituary."""
        result = extract_facts_with_rules(maxine_obit)

        # Check deceased person
        deceased = next((p for p in result['persons'] if p['role'] == 'deceased_primary'), None)
        assert deceased is not None
        assert deceased['given_names'] == 'Maxine V.'
        assert deceased['surname'] == 'Kaczmarowski'
        assert deceased['maiden_name'] == 'Paradowski'

        # Check death facts
        death_age_fact = next((f for f in result['facts'] if f['fact_type'] == 'person_death_age'), None)
        assert death_age_fact is not None
        assert death_age_fact['fact_value'] == '87'

        # Check maiden name fact
        maiden_fact = next((f for f in result['facts'] if f['fact_type'] == 'maiden_name'), None)
        assert maiden_fact is not None
        assert maiden_fact['fact_value'] == 'Paradowski'

        # Check great-grandchild Finley
        person_names = [p['full_name'] for p in result['persons']]
        assert any('Finley' in p for p in person_names), "Finley not found"

        # Check son-in-law Steve
        steve = next((p for p in result['persons'] if 'Steve' in p['full_name']), None)
        assert steve is not None

        print(f"\nMaxine extraction: {len(result['persons'])} persons, {len(result['facts'])} facts")


class TestFactCounts:
    """Tests for fact count validation against ground truth."""

    @pytest.fixture
    def patricia_obit(self):
        test_data_dir = Path(__file__).parent / "test_data"
        with open(test_data_dir / "patricia_obit.txt") as f:
            return f.read()

    def test_patricia_fact_count(self, patricia_obit):
        """Test that Patricia extraction hits target fact count."""
        result = extract_facts_with_rules(patricia_obit)

        # Target: 29 facts (from ground truth)
        # We should be close to this target
        total_facts = len(result['facts'])
        total_persons = len(result['persons'])

        print(f"\nPatricia: {total_persons} persons, {total_facts} facts")

        # Assert we're extracting a reasonable number
        assert total_persons >= 12, f"Expected at least 12 persons, got {total_persons}"
        assert total_facts >= 20, f"Expected at least 20 facts, got {total_facts}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
