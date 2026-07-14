#!/usr/bin/env python3
"""
MCP PubMed Server - Search and retrieve biomedical literature from PubMed via NCBI E-utilities.
"""

import sys
import xml.etree.ElementTree as ET
from typing import Annotated, Any, Dict, List

import httpx
from pydantic import Field
from mcp.server.fastmcp import FastMCP

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def log(msg: str):
    print(msg, file=sys.stderr, flush=True)


mcp = FastMCP("pubmed")


@mcp.tool()
def search_pubmed(
    query: Annotated[str, Field(description="Search query (e.g. 'lung cancer CT segmentation', 'MONAI medical imaging')")],
    max_results: Annotated[int, Field(description="Maximum number of results to return (1-20)", ge=1, le=20)] = 5,
) -> List[Dict[str, Any]]:
    """Search PubMed for biomedical literature. Returns a list of articles with PMID, title, authors, journal, and year."""
    log(f"Searching PubMed: {query!r} (max {max_results})")

    with httpx.Client(timeout=15) as client:
        search_resp = client.get(f"{EUTILS_BASE}/esearch.fcgi", params={
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
        })
        search_resp.raise_for_status()
        pmids = search_resp.json().get("esearchresult", {}).get("idlist", [])

    if not pmids:
        return []

    log(f"Found PMIDs: {pmids}")

    with httpx.Client(timeout=15) as client:
        summary_resp = client.get(f"{EUTILS_BASE}/esummary.fcgi", params={
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json",
        })
        summary_resp.raise_for_status()
        data = summary_resp.json().get("result", {})

    results = []
    for pmid in pmids:
        item = data.get(pmid, {})
        if not item:
            continue
        authors = [a.get("name", "") for a in item.get("authors", [])[:3]]
        if len(item.get("authors", [])) > 3:
            authors.append("et al.")
        results.append({
            "pmid": pmid,
            "title": item.get("title", ""),
            "authors": ", ".join(authors),
            "journal": item.get("fulljournalname", item.get("source", "")),
            "year": item.get("pubdate", "")[:4],
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })

    return results


@mcp.tool()
def fetch_article(
    pmid: Annotated[str, Field(description="PubMed ID of the article to fetch (e.g. '38234567')")],
) -> Dict[str, Any]:
    """Fetch full details for a PubMed article including abstract, authors, journal, and publication date."""
    log(f"Fetching PubMed article: {pmid}")

    with httpx.Client(timeout=15) as client:
        resp = client.get(f"{EUTILS_BASE}/efetch.fcgi", params={
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml",
            "rettype": "abstract",
        })
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    article = root.find(".//PubmedArticle")
    if article is None:
        return {"error": f"Article {pmid} not found"}

    title_el = article.find(".//ArticleTitle")
    title = "".join(title_el.itertext()) if title_el is not None else ""

    abstract_parts = article.findall(".//AbstractText")
    if abstract_parts:
        abstract = " ".join("".join(el.itertext()) for el in abstract_parts)
    else:
        abstract = ""

    authors = []
    for author in article.findall(".//Author")[:6]:
        last = author.findtext("LastName", "")
        fore = author.findtext("ForeName", "")
        if last:
            authors.append(f"{last} {fore}".strip())
    if len(article.findall(".//Author")) > 6:
        authors.append("et al.")

    journal = article.findtext(".//Journal/Title") or article.findtext(".//ISOAbbreviation") or ""
    year = article.findtext(".//PubDate/Year") or article.findtext(".//PubDate/MedlineDate", "")[:4]
    doi_el = article.find(".//ArticleId[@IdType='doi']")
    doi = doi_el.text if doi_el is not None else ""

    return {
        "pmid": pmid,
        "title": title,
        "authors": ", ".join(authors),
        "journal": journal,
        "year": year,
        "abstract": abstract,
        "doi": doi,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
