#!/usr/bin/env python3
"""
MCP HPO Server - Search and retrieve Human Phenotype Ontology terms via the HPO API.
"""

import sys
from typing import Annotated, Any, Dict, List

import httpx
from pydantic import Field
from mcp.server.fastmcp import FastMCP

HPO_BASE = "https://hpo.jax.org/api/hpo"


def log(msg: str):
    print(msg, file=sys.stderr, flush=True)


mcp = FastMCP("hpo")


@mcp.tool()
def search_hpo_terms(
    query: Annotated[str, Field(description="Search query (e.g. 'seizure', 'abnormal lung', 'cardiac arrhythmia')")],
    max_results: Annotated[int, Field(description="Maximum number of results to return (1-20)", ge=1, le=20)] = 10,
) -> List[Dict[str, Any]]:
    """Search Human Phenotype Ontology (HPO) terms by text. Returns matching phenotype terms with their HPO IDs."""
    log(f"Searching HPO: {query!r}")

    with httpx.Client(timeout=15) as client:
        resp = client.get(f"{HPO_BASE}/search/", params={"q": query, "max": max_results})
        resp.raise_for_status()
        data = resp.json()

    results = []
    for term in data.get("terms", [])[:max_results]:
        results.append({
            "hpo_id": term.get("id", ""),
            "name": term.get("name", ""),
            "definition": term.get("definition", ""),
        })
    return results


@mcp.tool()
def get_hpo_term(
    hpo_id: Annotated[str, Field(description="HPO term ID (e.g. 'HP:0001250' or '0001250')")],
) -> Dict[str, Any]:
    """Get full details for an HPO term including definition, synonyms, and hierarchy information."""
    hpo_id = hpo_id.strip()
    if not hpo_id.startswith("HP:"):
        hpo_id = f"HP:{hpo_id}"
    log(f"Fetching HPO term: {hpo_id}")

    with httpx.Client(timeout=15) as client:
        resp = client.get(f"{HPO_BASE}/term/{hpo_id}")
        resp.raise_for_status()
        data = resp.json()

    term = data.get("details", data)
    return {
        "hpo_id": term.get("id", hpo_id),
        "name": term.get("name", ""),
        "definition": term.get("definition", ""),
        "synonyms": [s.get("name", s) if isinstance(s, dict) else s for s in term.get("synonyms", [])],
        "comment": term.get("comment", ""),
    }


@mcp.tool()
def get_hpo_children(
    hpo_id: Annotated[str, Field(description="HPO term ID to get more specific child terms for")],
) -> List[Dict[str, Any]]:
    """Get child terms (more specific subtypes) of an HPO term."""
    hpo_id = hpo_id.strip()
    if not hpo_id.startswith("HP:"):
        hpo_id = f"HP:{hpo_id}"
    log(f"Fetching children of: {hpo_id}")

    with httpx.Client(timeout=15) as client:
        resp = client.get(f"{HPO_BASE}/term/{hpo_id}/children")
        resp.raise_for_status()
        data = resp.json()

    return [
        {"hpo_id": t.get("id", ""), "name": t.get("name", "")}
        for t in data.get("children", [])
    ]


@mcp.tool()
def get_hpo_parents(
    hpo_id: Annotated[str, Field(description="HPO term ID to get broader parent terms for")],
) -> List[Dict[str, Any]]:
    """Get parent terms (broader categories) of an HPO term."""
    hpo_id = hpo_id.strip()
    if not hpo_id.startswith("HP:"):
        hpo_id = f"HP:{hpo_id}"
    log(f"Fetching parents of: {hpo_id}")

    with httpx.Client(timeout=15) as client:
        resp = client.get(f"{HPO_BASE}/term/{hpo_id}/parents")
        resp.raise_for_status()
        data = resp.json()

    return [
        {"hpo_id": t.get("id", ""), "name": t.get("name", "")}
        for t in data.get("parents", [])
    ]


@mcp.tool()
def get_diseases_for_hpo_term(
    hpo_id: Annotated[str, Field(description="HPO term ID to find associated diseases for")],
    max_results: Annotated[int, Field(description="Maximum number of diseases to return (1-20)", ge=1, le=20)] = 10,
) -> List[Dict[str, Any]]:
    """Get diseases associated with an HPO phenotype term."""
    hpo_id = hpo_id.strip()
    if not hpo_id.startswith("HP:"):
        hpo_id = f"HP:{hpo_id}"
    log(f"Fetching diseases for: {hpo_id}")

    with httpx.Client(timeout=15) as client:
        resp = client.get(f"{HPO_BASE}/term/{hpo_id}/diseases")
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "disease_id": d.get("diseaseId", ""),
            "disease_name": d.get("diseaseName", ""),
            "db": d.get("db", ""),
        }
        for d in data.get("diseases", [])[:max_results]
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")
