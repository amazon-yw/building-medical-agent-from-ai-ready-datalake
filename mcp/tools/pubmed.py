"""PubMed research search tools using NCBI E-utilities API."""
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _esearch(query: str, max_results: int = 10) -> list[str]:
    params = urllib.parse.urlencode({
        "db": "pubmed", "term": query, "retmax": max_results,
        "retmode": "json", "sort": "relevance",
    })
    with urllib.request.urlopen(f"{ESEARCH_URL}?{params}", timeout=15) as resp:
        data = json.loads(resp.read())
    return data.get("esearchresult", {}).get("idlist", [])


def _efetch(pmids: list[str]) -> list[dict]:
    params = urllib.parse.urlencode({
        "db": "pubmed", "id": ",".join(pmids), "retmode": "xml",
    })
    with urllib.request.urlopen(f"{EFETCH_URL}?{params}", timeout=30) as resp:
        root = ET.fromstring(resp.read())

    articles = []
    for article in root.findall(".//PubmedArticle"):
        mc = article.find(".//MedlineCitation")
        pmid = mc.findtext("PMID", "")
        art = mc.find("Article")
        title = art.findtext("ArticleTitle", "") if art is not None else ""
        abstract_parts = art.findall(".//AbstractText") if art is not None else []
        abstract = " ".join(t.text or "" for t in abstract_parts)
        journal = art.findtext(".//Journal/Title", "") if art is not None else ""

        # Publication date
        pd = art.find(".//Journal/JournalIssue/PubDate") if art is not None else None
        pub_date = f"{pd.findtext('Year', '')}-{pd.findtext('Month', '')}-{pd.findtext('Day', '')}".strip("-") if pd is not None else ""

        # Authors (first 5)
        authors = []
        for au in (art.findall(".//AuthorList/Author") if art is not None else [])[:5]:
            last = au.findtext("LastName", "")
            fore = au.findtext("ForeName", "")
            if last:
                authors.append(f"{last} {fore}".strip())

        articles.append({
            "pmid": pmid,
            "title": title,
            "abstract": abstract[:1000] if abstract else "",
            "journal": journal,
            "pub_date": pub_date,
            "authors": authors,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })
    return articles


def search_pubmed(query: str, max_results: int = 5) -> list[dict]:
    """Search PubMed for research articles matching the query."""
    pmids = _esearch(query, max_results=min(max_results, 20))
    if not pmids:
        return []
    return _efetch(pmids)


def get_pubmed_article(pmid: str) -> dict:
    """Fetch a specific PubMed article by PMID with full abstract."""
    articles = _efetch([pmid])
    return articles[0] if articles else {"error": f"Article {pmid} not found"}
