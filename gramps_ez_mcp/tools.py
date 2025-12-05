#!/usr/bin/env python3
"""
Gramps tools for MCP server.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import sys
from gramps_ez_mcp.utils import format_datetime
from gramps_ez_mcp.session import gramps_database, get_session_context
from gramps_ez_mcp.cache import cached


def _get_state(metadata):
    if metadata["running"]:
        return "running"

    if metadata["hasCrashed"]:
        return "crashed"

    return "finished"


def _get_cache_info() -> Dict[str, Any]:
    """
    Get information about the current cache state.

    Returns:
        Dictionary containing cache statistics and session information.
    """
    from gramps_ez_mcp.cache import get_cache_info

    return get_cache_info()


def _clear_cache(func_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Clear cache entries.

    Args:
        func_name: Optional function name to clear cache for. If None, clears all caches.

    Returns:
        Dictionary with operation status.
    """
    from gramps_ez_mcp.cache import cache_invalidate

    try:
        cache_invalidate(func_name)
        return {
            "status": "success",
            "message": f"Cache cleared for {'all functions' if func_name is None else func_name}",
            "func_name": func_name,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to clear cache: {str(e)}",
            "func_name": func_name,
        }


# Tools:
# @cached(ttl_seconds=300)  # Cache for 5 minutes
# @cached(ttl_seconds=3600)  # Cache for 1 hour
# @cached(ttl_seconds=1800)  # Cache for 30 minutes
# @cached(ttl_seconds=600)  # Cache for 10 minutes


@cached(ttl_seconds=300)  # Cache for 5 minutes
def get_person(person_handle: str) -> Dict[str, Any]:
    """
    Given a person's handle, get the data dictionary of that person.
    """
    with gramps_database() as db:
        data = dict(db.get_raw_person_data(person_handle))
        return data


@cached(ttl_seconds=300)  # Cache for 5 minutes
def search_people_by_name(
    name: str, page: int = 1, page_size: int = 10
) -> List[Dict[str, Any]]:
    """
    Search for people in the Gramps database by name (partial match) with pagination.

    This function performs a search using Gramps' filter system to find
    people whose names contain ALL parts of the given search string. The search name
    is split by spaces, and all parts must be found in the person's name fields.
    The search is case-insensitive and matches against first names, surnames,
    nicknames, titles, suffixes, and other name fields.

    Args:
        name: The name or partial name to search for. Multiple words are split by spaces,
              and ALL parts must match (case-insensitive substring match).
              Example: "John Smith" will match people with both "John" and "Smith" in their name.
        page: Page number to return (1-indexed). Default is 1.
        page_size: Number of results per page. Default is 10.

    Returns:
        A list of dictionaries, each containing the person data for matching people
        for the requested page. Each dictionary has the same structure as returned by get_person().
    """
    from gramps.gen.filters import GenericFilter
    from gramps.gen.filters.rules.person import SearchName

    # Validate pagination parameters
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10

    # Split the name by spaces and filter out empty strings
    name_parts = [part.strip() for part in name.split() if part.strip()]

    # If no valid name parts, return empty results
    if not name_parts:
        return []

    with gramps_database() as db:
        # Create a filter with AND logic to require all name parts match
        name_filter = GenericFilter()
        name_filter.set_logical_op("and")

        # Add a SearchName rule for each part of the name
        for name_part in name_parts:
            search_rule = SearchName([name_part])
            name_filter.add_rule(search_rule)

        # Get all person handles and filter them
        matching_handles = []
        for person_handle in db.get_person_handles():
            if name_filter.match(person_handle, db):
                matching_handles.append(person_handle)

        # Calculate pagination indices
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        # Get the page of handles
        page_handles = matching_handles[start_idx:end_idx]

        # Convert handles to person data dictionaries
        results = []
        for handle in page_handles:
            data = dict(db.get_raw_person_data(handle))
            results.append(data)

        return results


@cached(ttl_seconds=300)  # Cache for 5 minutes
def get_mother_of_person(person_handle: str) -> Dict[str, Any]:
    """
    Given a person's handle, return their mother's data dictionary.
    """
    with gramps_database() as db:
        person_obj = db.get_person_from_handle(person_handle)
        obj = db.sa.mother(person_obj)
        data = dict(db.get_raw_person_data(obj.handle))
        return data


@cached(ttl_seconds=300)  # Cache for 5 minutes
def get_family(family_handle: str) -> Dict[str, Any]:
    """
    Get a family's data given the family handle. Note that family
    handles are different from a person handle. You can use a person's
    family data to get the family handle.
    """
    with gramps_database() as db:
        data = dict(db.get_raw_family_data(family_handle))
        return data


@cached(ttl_seconds=300)  # Cache for 5 minutes
def get_home_person() -> Dict[str, Any]:
    """
    Get the home person data.
    """
    with gramps_database() as db:
        obj = db.get_default_person()
        if obj:
            data = dict(db._get_raw_person_from_id_data(obj.gramps_id))
            return data
        return None


@cached(ttl_seconds=300)  # Cache for 5 minutes
def get_children_of_person(person_handle: str) -> List[str]:
    """
    Get a list of children handles of a person's main family,
    given a person's handle.
    """
    with gramps_database() as db:
        obj = db.get_person_from_handle(person_handle)
        family_handle_list = obj.get_family_handle_list()
        if family_handle_list:
            family_id = family_handle_list[0]
            family = db.get_family_from_handle(family_id)
            return [handle.ref for handle in family.get_child_ref_list()]
        else:
            return []


@cached(ttl_seconds=300)  # Cache for 5 minutes
def get_father_of_person(person_handle: str) -> Dict[str, Any]:
    """
    Given a person's handle, return their father's data dictionary.
    """
    with gramps_database() as db:
        person_obj = db.get_person_from_handle(person_handle)
        obj = db.sa.father(person_obj)
        data = dict(db.get_raw_person_data(obj.handle))
        return data


@cached(ttl_seconds=300)  # Cache for 5 minutes
def get_person_birth_date(person_handle: str) -> str:
    """
    Given a person's handle, return the birth date as a string.
    """
    with gramps_database() as db:
        person = db.get_person_from_handle(person_handle)
        return db.sa.birth_date(person)


@cached(ttl_seconds=300)  # Cache for 5 minutes
def get_person_death_date(person_handle: str) -> str:
    """
    Given a person's handle, return the death date as a string.
    """
    with gramps_database() as db:
        person = db.get_person_from_handle(person_handle)
        return db.sa.death_date(person)


@cached(ttl_seconds=300)  # Cache for 5 minutes
def get_person_birth_place(person_handle: str) -> str:
    """
    Given a person's handle, return the birth date as a string.
    """
    with gramps_database() as db:
        person = db.get_person_from_handle(person_handle)
        return db.sa.birth_place(person)


@cached(ttl_seconds=300)  # Cache for 5 minutes
def get_person_death_place(person_handle: str) -> str:
    """
    Given a person's handle, return the death place as a string.
    """
    with gramps_database() as db:
        person = db.get_person_from_handle(person_handle)
        return db.sa.death_place(person)


@cached(ttl_seconds=300)  # Cache for 5 minutes
def get_person_event_list(person_handle: str) -> List[str]:
    """
    Get a list of event handles associated with a person,
    given the person handle. Use `get_event(event_handle)`
    to look up details about an event.
    """
    with gramps_database() as db:
        obj = db.get_person_from_handle(person_handle)
        if obj:
            return [ref.ref for ref in obj.get_event_ref_list()]


@cached(ttl_seconds=300)  # Cache for 5 minutes
def get_event(event_handle: str) -> Dict[str, Any]:
    """
    Given an event_handle, get the associated data dictionary.
    """
    with gramps_database() as db:
        data = dict(db.get_raw_event_data(event_handle))
        return data


@cached(ttl_seconds=300)  # Cache for 5 minutes
def get_event_place(event_handle: str) -> str:
    """
    Given an event_handle, return the associated place string.
    """
    with gramps_database() as db:
        event = db.get_event_from_handle(event_handle)
        return place_displayer.display_event(db, event)


def _initialize():
    from gramps_ez_mcp.session import initialize_session

    initialize_session()
