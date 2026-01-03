"""
Gramps Web API client for SSOT integration.

This service provides read-only access to Gramps Web in Phase 3 Stage 1.
Future stages will add write capabilities.
"""

import os
import requests
from typing import List, Dict, Optional, Any
from datetime import datetime


class GrampsClient:
    """
    Client for Gramps Web REST API.

    Phase 3 Stage 1: Read-only operations (search, fetch)
    Future: Write operations (create, update)
    """

    def __init__(self, base_url: str = None, api_token: str = None):
        self.base_url = base_url or os.getenv('GRAMPS_WEB_URL', 'http://grampsweb:5000')
        self.api_token = api_token or os.getenv('GRAMPS_API_TOKEN')
        self.username = os.getenv('GRAMPS_USERNAME')
        self.password = os.getenv('GRAMPS_PASSWORD')

        # Remove trailing slash
        self.base_url = self.base_url.rstrip('/')

        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })

        # Try to authenticate if we have credentials
        if not self.api_token and self.username and self.password:
            self._authenticate()
        elif self.api_token:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_token}'
            })

    def _authenticate(self) -> bool:
        """
        Authenticate with Gramps Web using username/password to get JWT token.

        Returns:
            True if authentication successful
        """
        try:
            url = f"{self.base_url}/api/token/"
            response = self.session.post(
                url,
                json={'username': self.username, 'password': self.password}
            )
            response.raise_for_status()
            data = response.json()

            self.api_token = data.get('access_token')
            if self.api_token:
                self.session.headers.update({
                    'Authorization': f'Bearer {self.api_token}'
                })
                print(f"Gramps Web authenticated successfully")
                return True
            return False
        except Exception as e:
            print(f"Gramps authentication failed: {e}")
            return False

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        Make HTTP request to Gramps Web API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments for requests

        Returns:
            JSON response as dict

        Raises:
            Exception: If request fails
        """
        url = f"{self.base_url}/api{endpoint}"

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Gramps API error: {method} {endpoint} - {e}")
            raise Exception(f"Gramps API request failed: {e}")

    def health_check(self) -> bool:
        """
        Check if Gramps Web is accessible.

        Returns:
            True if Gramps Web is responding
        """
        try:
            response = self._request('GET', '/metadata')
            return 'database' in response or 'gramps_version' in response
        except:
            return False

    def search_people(
        self,
        query: str = None,
        surname: str = None,
        given_name: str = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Search for people in Gramps Web.

        Args:
            query: General search query
            surname: Filter by surname
            given_name: Filter by given name
            limit: Maximum results to return

        Returns:
            List of person objects
        """
        # Fetch all people (Gramps Web API doesn't support name filtering)
        params = {'pagesize': 1000}  # Get all people

        try:
            # Gramps Web search endpoint
            response = self._request('GET', '/people/', params=params)

            # Handle different response formats
            if isinstance(response, list):
                people = response
            elif isinstance(response, dict) and 'data' in response:
                people = response['data']
            else:
                return []

            # Client-side filtering (Gramps Web doesn't support server-side name filtering)
            results = []
            for person in people:
                primary_name = person.get('primary_name', {})
                person_given = primary_name.get('first_name', '').lower()
                surname_list = primary_name.get('surname_list', [])
                person_surname = surname_list[0].get('surname', '').lower() if surname_list else ''
                full_name = f"{person_given} {person_surname}"

                # Apply filters
                if given_name and given_name.lower() not in person_given:
                    continue
                if surname and surname.lower() not in person_surname:
                    continue
                if query and query.lower() not in full_name:
                    continue

                results.append(person)

                if len(results) >= limit:
                    break

            return results
        except Exception as e:
            print(f"Search failed: {e}")
            return []

    def get_person(self, identifier: str) -> Optional[Dict]:
        """
        Get a specific person by handle or Gramps ID.

        Args:
            identifier: Gramps handle or person ID

        Returns:
            Person object or None if not found
        """
        try:
            # Try as handle first (Gramps Web API uses handles)
            return self._request('GET', f'/people/{identifier}')
        except:
            return None

    def get_person_events(self, handle: str) -> List[Dict]:
        """
        Get all events for a person by handle.

        Args:
            handle: Gramps person handle

        Returns:
            List of event objects
        """
        try:
            person = self.get_person(handle)
            if not person or 'event_ref_list' not in person:
                return []

            return self.get_person_events_from_person(person)
        except:
            return []

    def get_person_events_from_person(self, person: Dict) -> List[Dict]:
        """
        Get all events from a person object (avoids extra API call).

        Args:
            person: Gramps person object

        Returns:
            List of event objects
        """
        try:
            if not person or 'event_ref_list' not in person:
                return []

            events = []
            for event_ref in person.get('event_ref_list', []):
                event_id = event_ref.get('ref')
                if event_id:
                    try:
                        event = self._request('GET', f'/events/{event_id}')
                        if event:
                            events.append(event)
                    except:
                        pass  # Skip if event fetch fails

            return events
        except:
            return []

    def get_person_families(self, gramps_id: str) -> Dict[str, List[Dict]]:
        """
        Get all families for a person (as parent and as child).

        Args:
            gramps_id: Gramps person ID

        Returns:
            Dict with 'as_parent' and 'as_child' family lists
        """
        try:
            person = self.get_person(gramps_id)
            if not person:
                return {'as_parent': [], 'as_child': []}

            families = {'as_parent': [], 'as_child': []}

            # Families where person is parent
            for family_ref in person.get('parent_family_list', []):
                family_id = family_ref.get('ref') if isinstance(family_ref, dict) else family_ref
                if family_id:
                    family = self._request('GET', f'/families/{family_id}')
                    if family:
                        families['as_parent'].append(family)

            # Families where person is child
            for family_ref in person.get('child_ref_list', []):
                family_id = family_ref.get('ref') if isinstance(family_ref, dict) else family_ref
                if family_id:
                    family = self._request('GET', f'/families/{family_id}')
                    if family:
                        families['as_child'].append(family)

            return families
        except:
            return {'as_parent': [], 'as_child': []}

    def extract_person_facts(self, person: Dict) -> Dict[str, Any]:
        """
        Extract key facts from a Gramps person object for comparison.

        Args:
            person: Gramps person object

        Returns:
            Dict of extracted facts (name, dates, relationships, etc.)
        """
        facts = {
            'gramps_id': person.get('gramps_id'),
            'handle': person.get('handle'),
            'names': [],
            'gender': person.get('gender'),
            'birth_date': None,
            'death_date': None,
            'birth_place': None,
            'death_place': None
        }

        # Extract names
        primary_name = person.get('primary_name', {})
        if primary_name:
            facts['names'].append({
                'type': 'primary',
                'given': primary_name.get('first_name', ''),
                'surname': primary_name.get('surname_list', [{}])[0].get('surname', ''),
                'full': f"{primary_name.get('first_name', '')} {primary_name.get('surname_list', [{}])[0].get('surname', '')}".strip()
            })

        # Alternative names
        for alt_name in person.get('alternate_names', []):
            facts['names'].append({
                'type': 'alternate',
                'given': alt_name.get('first_name', ''),
                'surname': alt_name.get('surname_list', [{}])[0].get('surname', ''),
                'full': f"{alt_name.get('first_name', '')} {alt_name.get('surname_list', [{}])[0].get('surname', '')}".strip()
            })

        # Extract birth/death from events (use handle, not gramps_id)
        events = self.get_person_events_from_person(person)
        for event in events:
            event_type = event.get('type', {}).get('string', '') if isinstance(event.get('type'), dict) else event.get('type', '')

            if event_type.lower() == 'birth':
                date = event.get('date')
                if date:
                    facts['birth_date'] = self._format_gramps_date(date)
                place_handle = event.get('place')
                if place_handle:
                    facts['birth_place'] = place_handle

            elif event_type.lower() == 'death':
                date = event.get('date')
                if date:
                    facts['death_date'] = self._format_gramps_date(date)
                place_handle = event.get('place')
                if place_handle:
                    facts['death_place'] = place_handle

        return facts

    def _format_gramps_date(self, date_obj: Dict) -> Optional[str]:
        """
        Format Gramps date object to ISO string.

        Args:
            date_obj: Gramps date object

        Returns:
            ISO date string or None
        """
        try:
            if isinstance(date_obj, dict):
                # Gramps date format: {modifier, quality, dateval, text}
                dateval = date_obj.get('dateval')
                if dateval and len(dateval) >= 3:
                    year, month, day = dateval[2], dateval[1], dateval[0]
                    if year and month and day:
                        return f"{year:04d}-{month:02d}-{day:02d}"
                    elif year and month:
                        return f"{year:04d}-{month:02d}"
                    elif year:
                        return f"{year:04d}"
            return None
        except:
            return None

    # ========================================================================
    # WRITE OPERATIONS (Phase 3 Stage 2+)
    # ========================================================================

    def create_source(
        self,
        title: str,
        author: str = None,
        pubinfo: str = None,
        url: str = None
    ) -> Optional[Dict]:
        """
        Create a source record in Gramps.

        Args:
            title: Source title (e.g., "Obituary of John Smith")
            author: Author or publisher
            pubinfo: Publication information
            url: URL to source

        Returns:
            Created source object or None if failed
        """
        source_data = {
            'title': title,
        }

        if author:
            source_data['author'] = author
        if pubinfo:
            source_data['pubinfo'] = pubinfo

        # Add URL as attribute
        if url:
            source_data['attribute_list'] = [{
                'type': {'_class': 'SrcAttributeType', 'string': 'URL'},
                'value': url
            }]

        try:
            result = self._request('POST', '/sources/', json=source_data)
            # API may return a list with the created object, or just the object
            if isinstance(result, list) and len(result) > 0:
                # The response has nested 'new' object with the actual source
                item = result[0]
                if isinstance(item, dict) and 'new' in item:
                    return item['new']
                return item
            return result
        except Exception as e:
            print(f"Failed to create source: {e}")
            return None

    def create_citation(
        self,
        source_handle: str,
        page: str = None,
        confidence: int = 2,
        note: str = None
    ) -> Optional[Dict]:
        """
        Create a citation for a source.

        Args:
            source_handle: Gramps source handle (not ID - use handle from source object)
            page: Page reference or detail
            confidence: Confidence level (0=very low, 4=very high)
            note: Citation note (stored as page for simplicity)

        Returns:
            Created citation object or None if failed
        """
        citation_data = {
            'source_handle': source_handle,
            'confidence': confidence
        }

        # Use page field for the note/reference since note_list has complex format
        if page:
            citation_data['page'] = page
        elif note:
            citation_data['page'] = note

        try:
            result = self._request('POST', '/citations/', json=citation_data)
            # API may return a list with the created object, or just the object
            if isinstance(result, list) and len(result) > 0:
                # The response has nested 'new' object with the actual citation
                item = result[0]
                if isinstance(item, dict) and 'new' in item:
                    return item['new']
                return item
            return result
        except Exception as e:
            print(f"Failed to create citation: {e}")
            return None

    def add_citation_to_person(
        self,
        person_handle: str,
        citation_handle: str
    ) -> bool:
        """
        Add a citation to a person record.

        Args:
            person_handle: Gramps person handle
            citation_handle: Gramps citation handle

        Returns:
            True if successful
        """
        try:
            # Get current person
            person = self.get_person(person_handle)
            if not person:
                return False

            # Get citation list
            citation_list = person.get('citation_list', [])

            # Check if citation already exists
            if citation_handle in citation_list:
                print(f"Citation already exists on person")
                return True

            # Add citation
            citation_list.append(citation_handle)

            # Update person
            update_data = {'citation_list': citation_list}
            self._request('PUT', f'/people/{person_handle}', json=update_data)

            return True
        except Exception as e:
            print(f"Failed to add citation to person: {e}")
            return False

    def find_or_create_source(
        self,
        title: str,
        url: str,
        author: str = None,
        pubinfo: str = None
    ) -> Optional[tuple]:
        """
        Find existing source by title/URL or create new one.

        Args:
            title: Source title
            url: Source URL
            author: Author
            pubinfo: Publication info

        Returns:
            Tuple of (gramps_id, handle) or None if failed
        """
        try:
            # Get all sources and search locally (API may not support search params)
            sources = self._request('GET', '/sources/')

            if isinstance(sources, dict) and 'data' in sources:
                sources = sources['data']

            # Make sure sources is a list
            if not isinstance(sources, list):
                sources = []

            # Check if any match our URL
            for source in sources:
                if not isinstance(source, dict):
                    continue
                for attr in source.get('attribute_list', []):
                    if not isinstance(attr, dict):
                        continue
                    attr_type = attr.get('type', {})
                    if isinstance(attr_type, dict):
                        type_str = attr_type.get('string', '')
                    else:
                        type_str = str(attr_type)
                    if type_str == 'URL' and attr.get('value') == url:
                        return (source.get('gramps_id'), source.get('handle'))

            # Not found, create new
            new_source = self.create_source(
                title=title,
                author=author,
                pubinfo=pubinfo,
                url=url
            )

            if new_source:
                return (new_source.get('gramps_id'), new_source.get('handle'))

            return None
        except Exception as e:
            print(f"Error finding/creating source: {e}")
            import traceback
            traceback.print_exc()
            return None
