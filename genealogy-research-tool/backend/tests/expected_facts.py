"""
Expected facts from the 3 test obituaries.

This serves as the acceptance criteria for Phase 1.
"""

# ============================================================================
# PATRICIA'S OBITUARY - EXPECTED EXTRACTIONS
# ============================================================================

PATRICIA_EXPECTED_PERSONS = [
    {
        "full_name": "Patricia L. Blundon",
        "given_names": "Patricia L.",
        "surname": "Blundon",
        "maiden_name": "Kaczmarowski",
        "nickname": "Patsy",
        "role": "deceased_primary",
        "is_deceased": True
    },
    {
        "full_name": "Steven Blundon",
        "given_names": "Steven",
        "surname": "Blundon",
        "role": "spouse",
        "spouse_of": "Patricia L. Blundon"
    },
    {
        "full_name": "Ryan Blundon",
        "given_names": "Ryan",
        "surname": "Blundon",
        "role": "child",
        "spouse_of": "Amy Blundon"
    },
    {
        "full_name": "Amy Blundon",
        "given_names": "Amy",
        "surname": "Blundon",
        "role": "child",
        "spouse_of": "Ryan Blundon"
    },
    {
        "full_name": "Megan Wurz",
        "given_names": "Megan",
        "surname": "Wurz",
        "role": "child",
        "spouse_of": "Ross Wurz"
    },
    {
        "full_name": "Ross Wurz",
        "given_names": "Ross",
        "surname": "Wurz",
        "role": "in_law",
        "spouse_of": "Megan Wurz"
    },
    {
        "full_name": "Autumn",
        "given_names": "Autumn",
        "surname": "UNKNOWN",
        "role": "grandchild",
        "age": "5"
    },
    {
        "full_name": "Caralyn",
        "given_names": "Caralyn",
        "surname": "UNKNOWN",
        "role": "grandchild",
        "age": "3"
    },
    {
        "full_name": "Terrence Kaczmarowski",
        "given_names": "Terrence",
        "surname": "Kaczmarowski",
        "role": "parent"
    },
    {
        "full_name": "Maxine Kaczmarowski",
        "given_names": "Maxine",
        "surname": "Kaczmarowski",
        "role": "parent"
    },
    {
        "full_name": "Marty Blundon",
        "given_names": "Marty",
        "surname": "Blundon",
        "role": "in_law",
        "spouse_of": "Katie Blundon"
    },
    {
        "full_name": "Katie Blundon",
        "given_names": "Katie",
        "surname": "Blundon",
        "role": "in_law",
        "spouse_of": "Marty Blundon"
    },
    {
        "full_name": "Monica Clasen",
        "given_names": "Monica",
        "surname": "Clasen",
        "role": "in_law",
        "spouse_of": "Ron Clasen"
    },
    {
        "full_name": "Ron Clasen",
        "given_names": "Ron",
        "surname": "Clasen",
        "role": "in_law",
        "spouse_of": "Monica Clasen"
    }
]

PATRICIA_EXPECTED_KEY_FACTS = [
    {
        "fact_type": "person_death_date",
        "subject_name": "Patricia L. Blundon",
        "fact_value": "August 7, 2008",
        "confidence_score": 1.0
    },
    {
        "fact_type": "person_death_age",
        "subject_name": "Patricia L. Blundon",
        "fact_value": "57",
        "confidence_score": 1.0
    },
    {
        "fact_type": "maiden_name",
        "subject_name": "Patricia L. Blundon",
        "fact_value": "Kaczmarowski",
        "confidence_score": 1.0
    },
    {
        "fact_type": "person_nickname",
        "subject_name": "Patricia L. Blundon",
        "fact_value": "Patsy",
        "confidence_score": 1.0
    },
    {
        "fact_type": "marriage_duration",
        "subject_name": "Patricia L. Blundon",
        "fact_value": "38 years",
        "related_name": "Steven Blundon",
        "confidence_score": 1.0
    },
    {
        "fact_type": "relationship",
        "subject_name": "Patricia L. Blundon",
        "fact_value": "daughter",
        "related_name": "Terrence Kaczmarowski",
        "relationship_type": "parent-child",
        "confidence_score": 1.0
    },
    {
        "fact_type": "relationship",
        "subject_name": "Patricia L. Blundon",
        "fact_value": "daughter",
        "related_name": "Maxine Kaczmarowski",
        "relationship_type": "parent-child",
        "confidence_score": 1.0
    }
]

# ============================================================================
# TERRENCE'S OBITUARY - EXPECTED EXTRACTIONS
# ============================================================================

TERRENCE_EXPECTED_PERSONS = [
    {
        "full_name": "Terrence E. Kaczmarowski",
        "given_names": "Terrence E.",
        "surname": "Kaczmarowski",
        "role": "deceased_primary",
        "is_deceased": True
    },
    {
        "full_name": "Maxine Kaczmarowski",
        "given_names": "Maxine",
        "surname": "Kaczmarowski",
        "maiden_name": "Paradowski",
        "role": "spouse"
    },
    {
        "full_name": "Patricia Blundon",
        "given_names": "Patricia",
        "surname": "Blundon",
        "role": "child",
        "is_deceased": True,  # "the late Patricia"
        "spouse_of": "Steve Blundon"
    },
    {
        "full_name": "Steve Blundon",
        "given_names": "Steve",
        "surname": "Blundon",
        "role": "in_law"
    }
]

TERRENCE_EXPECTED_KEY_FACTS = [
    {
        "fact_type": "person_death_date",
        "subject_name": "Terrence E. Kaczmarowski",
        "fact_value": "December 18, 2008",
        "confidence_score": 1.0
    },
    {
        "fact_type": "person_death_age",
        "subject_name": "Terrence E. Kaczmarowski",
        "fact_value": "80",
        "confidence_score": 1.0
    },
    {
        "fact_type": "preceded_in_death",
        "subject_name": "Patricia Blundon",
        "fact_value": "deceased before primary",
        "is_inferred": True,
        "inference_basis": "'the late Patricia' indicates she died before Terrence"
    }
]

# ============================================================================
# MAXINE'S OBITUARY - EXPECTED EXTRACTIONS
# ============================================================================

MAXINE_EXPECTED_PERSONS = [
    {
        "full_name": "Maxine V. Kaczmarowski",
        "given_names": "Maxine V.",
        "surname": "Kaczmarowski",
        "maiden_name": "Paradowski",
        "role": "deceased_primary",
        "is_deceased": True
    },
    {
        "full_name": "Terrence Kaczmarowski",
        "given_names": "Terrence",
        "surname": "Kaczmarowski",
        "role": "spouse",
        "is_deceased": True  # "Reunited with her husband Terrence"
    },
    {
        "full_name": "Patricia",
        "given_names": "Patricia",
        "role": "child",
        "is_deceased": True  # "Reunited with... daughter Patricia"
    },
    {
        "full_name": "Steve Blundon",
        "given_names": "Steve",
        "surname": "Blundon",
        "role": "in_law"
    },
    {
        "full_name": "Finley",
        "given_names": "Finley",
        "role": "great_grandchild"
    }
]

MAXINE_EXPECTED_KEY_FACTS = [
    {
        "fact_type": "person_death_date",
        "subject_name": "Maxine V. Kaczmarowski",
        "fact_value": "May 24, 2018",
        "confidence_score": 1.0
    },
    {
        "fact_type": "person_death_age",
        "subject_name": "Maxine V. Kaczmarowski",
        "fact_value": "87",
        "confidence_score": 1.0
    },
    {
        "fact_type": "maiden_name",
        "subject_name": "Maxine V. Kaczmarowski",
        "fact_value": "Paradowski",
        "confidence_score": 1.0
    },
    {
        "fact_type": "preceded_in_death",
        "subject_name": "Terrence Kaczmarowski",
        "fact_value": "deceased before primary",
        "is_inferred": True,
        "inference_basis": "'Reunited with her husband Terrence'"
    },
    {
        "fact_type": "preceded_in_death",
        "subject_name": "Patricia",
        "fact_value": "deceased before primary",
        "is_inferred": True,
        "inference_basis": "'Reunited with... daughter Patricia'"
    }
]

# ============================================================================
# CROSS-OBITUARY VALIDATION
# ============================================================================

# Same people across obituaries (for fuzzy matching validation)
CROSS_OBIT_SAME_PERSONS = [
    {
        "canonical_name": "Ryan Blundon",
        "variants": [
            "Ryan (Amy) Blundon",  # Maxine's obit
            "Ryan (Amy)",  # Terrence's obit
            "Ryan (Amy)"  # Patricia's obit
        ],
        "appears_in": ["patricia", "terrence", "maxine"]
    },
    {
        "canonical_name": "Megan Wurz",
        "variants": [
            "Megan (Ross) Wurz"
        ],
        "appears_in": ["patricia", "terrence", "maxine"]
    },
    {
        "canonical_name": "Steven Blundon",
        "variants": [
            "Steven",  # Patricia's obit ("wife of Steven")
            "Steve Blundon",  # Terrence's obit ("Patricia (Steve) Blundon")
            "Steve Blundon"  # Maxine's obit
        ],
        "appears_in": ["patricia", "terrence", "maxine"]
    }
]

# Spelling variants that require fuzzy matching
FUZZY_MATCH_CASES = [
    {
        "name1": "Rose Mary Paradowski",  # Terrence's obit
        "name2": "Rosemary Paradowski",  # Maxine's obit
        "expected_match": True,
        "expected_score_min": 0.85
    },
    {
        "name1": "Steve Blundon",
        "name2": "Steven Blundon",
        "expected_match": True,
        "expected_score_min": 0.85
    }
]

# Timeline validations
TIMELINE_VALIDATIONS = [
    {
        "person": "Patricia Blundon",
        "death_date": "August 7, 2008",
        "validation": "died BEFORE father Terrence (December 18, 2008)"
    },
    {
        "person": "Terrence E. Kaczmarowski",
        "death_date": "December 18, 2008",
        "validation": "obit says 'the late Patricia' confirming Patricia died first"
    },
    {
        "person": "Finley",
        "first_mention": "maxine_obit",
        "validation": "Not in 2008 obits (Patricia, Terrence) - born after 2008"
    }
]
