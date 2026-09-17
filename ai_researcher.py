import requests
from bs4 import BeautifulSoup
import sqlite3
import json
import re
from datetime import datetime


OFFICIAL_SOURCES = {
    "seed": [
        {
            "name": "SATHI - Seed Authentication, Traceability & Holistic Inventory",
            "url": "https://www.india.gov.in/category/agriculture-rural-environment/subcategory/resources-for-agriculture/details/website-of-seed-authentication-traceability-holistic-inventory-sathi"
        },
        {
            "name": "Seednet India Portal",
            "url": "https://www.india.gov.in/category/agriculture-rural-environment/subcategory/resources-for-agriculture/details/seednet-india-portal"
        },
        {
            "name": "Andhra Pradesh State Seed Certification Agency",
            "url": "https://www.india.gov.in/category/agriculture-rural-environment/subcategory/resources-for-agriculture/details/website-of-andhra-pradesh-state-seed-certification-agency"
        },
        {
            "name": "National Seed Testing Laboratory",
            "url": "https://www.india.gov.in/category/agriculture-rural-environment/subcategory/resources-for-agriculture/details/online-information-of-national-seed-testing-laboratory-by-department-of-agriculture-and-farmers-welfare-of-ministry-of-agriculture"
        }
    ],

    "fertilizer": [
        {
            "name": "Department of Fertilizers",
            "url": "https://www.fert.nic.in/"
        }
    ]
}


RESEARCH_KEYWORDS = [
    "seed",
    "fertilizer",
    "authentication",
    "traceability",
    "testing",
    "certification",
    "quality",
    "registration",
    "dealer",
    "batch",
    "label",
    "genuine",
    "counterfeit",
    "fake",
    "spurious",
    "standards",
    "government"
]


def clean_url(url):
    if not url:
        return ""

    match = re.search(
        r"https?://[^\s\]\)]+",
        url
    )

    if match:
        return match.group(0)

    return url.strip()


def clean_sentence(text):
    if not text:
        return ""

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    unwanted_patterns = [
        "Okay Cancel Close",
        "Search Area",
        "Search All Categories",
        "Accessibility Tools",
        "Contrast Adjustment",
        "High Contrast",
        "Normal Text Size",
        "Increase Text",
        "Decrease Text",
        "Text Reset",
        "Text Spacing",
        "Line Height",
        "Hide Images",
        "Big Cursor",
        "Screen Reader",
        "Loading",
        "Translation Feedback",
        "CPGRAMS",
        "Calendar Share",
        "Colour Color",
        "All Acts Citizen Engagements",
        "Directory Explore India",
        "Search Close",
        "Select a holiday",
        "View More"
    ]

    for pattern in unwanted_patterns:
        text = text.replace(
            pattern,
            ""
        )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text


def fetch_webpage(url):
    try:
        url = clean_url(url)

        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "Chrome/120.0 Safari/537.36"
                )
            }
        )

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type",
            ""
        ).lower()

        if "pdf" in content_type:
            return ""

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        for element in soup(
            [
                "script",
                "style",
                "noscript",
                "header",
                "footer",
                "nav",
                "form",
                "button"
            ]
        ):
            element.decompose()

        main_content = soup.find(
            "main"
        )

        if main_content:
            text = main_content.get_text(
                separator=" ",
                strip=True
            )
        else:
            text = soup.get_text(
                separator=" ",
                strip=True
            )

        text = clean_sentence(text)

        return text

    except Exception as error:
        print(
            "Research source error:",
            error
        )

        return ""


def get_sources(product_type):
    product_type = (
        product_type or ""
    ).lower()

    if "fertilizer" in product_type:
        return OFFICIAL_SOURCES["fertilizer"]

    return OFFICIAL_SOURCES["seed"]


def split_into_sentences(text):
    if not text:
        return []

    text = clean_sentence(text)

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    result = []

    for sentence in sentences:

        sentence = clean_sentence(
            sentence
        )

        if len(sentence) >= 40:
            result.append(sentence)

    return result


def find_relevant_sentences(
    text,
    product_name,
    company,
    batch_no
):
    if not text:
        return []

    sentences = split_into_sentences(
        text
    )

    relevant = []

    search_terms = []

    if product_name:
        search_terms.append(
            product_name.lower()
        )

    if company:
        search_terms.append(
            company.lower()
        )

    if batch_no:
        search_terms.append(
            batch_no.lower()
        )

    search_terms.extend(
        RESEARCH_KEYWORDS
    )

    for sentence in sentences:

        lower_sentence = (
            sentence.lower()
        )

        matches = 0

        for term in search_terms:

            if term and term in lower_sentence:
                matches += 1

        if matches > 0:

            relevant.append({
                "text": sentence,
                "matches": matches
            })

    relevant.sort(
        key=lambda item: item["matches"],
        reverse=True
    )

    final_sentences = []

    seen = set()

    for item in relevant:

        sentence = item["text"]

        key = sentence.lower()

        if key in seen:
            continue

        seen.add(key)

        final_sentences.append(
            sentence
        )

        if len(final_sentences) >= 5:
            break

    return final_sentences


def create_farmer_friendly_evidence(
    source_name,
    relevant_sentences,
    product_found,
    company_found,
    batch_found
):
    evidence = []

    if batch_found:

        evidence.append(
            "The submitted batch number was found in the official source."
        )

    elif product_found and company_found:

        evidence.append(
            "The submitted product name and company information were found in the official source."
        )

    elif product_found:

        evidence.append(
            "The submitted product name was found in the official source."
        )

    elif company_found:

        evidence.append(
            "The submitted company name was found in the official source."
        )

    if relevant_sentences:

        for sentence in relevant_sentences:

            sentence = clean_sentence(
                sentence
            )

            if not sentence:
                continue

            if sentence not in evidence:
                evidence.append(
                    sentence
                )

            if len(evidence) >= 3:
                break

    if not evidence:

        evidence.append(
            "This official source contains agricultural information relevant to product verification, but no direct product-level match was found."
        )

    return evidence


def collect_official_evidence(
    product_type,
    product_name,
    company,
    batch_no
):
    sources = get_sources(
        product_type
    )

    evidence = []

    for source in sources:

        source_url = clean_url(
            source["url"]
        )

        text = fetch_webpage(
            source_url
        )

        text_lower = text.lower()

        product_found = (
            bool(product_name)
            and product_name.lower()
            in text_lower
        )

        company_found = (
            bool(company)
            and company.lower()
            in text_lower
        )

        batch_found = (
            bool(batch_no)
            and batch_no.lower()
            in text_lower
        )

        relevant_sentences = (
            find_relevant_sentences(
                text,
                product_name,
                company,
                batch_no
            )
        )

        farmer_evidence = (
            create_farmer_friendly_evidence(
                source["name"],
                relevant_sentences,
                product_found,
                company_found,
                batch_found
            )
        )

        evidence.append({
            "source": source["name"],
            "url": source_url,
            "product_found": product_found,
            "company_found": company_found,
            "batch_found": batch_found,
            "relevant_information": farmer_evidence
        })

    return evidence


def analyze_research_evidence(
    product_type,
    product_name,
    company,
    batch_no,
    evidence
):
    product_matches = 0
    company_matches = 0
    batch_matches = 0
    useful_sources = 0

    for item in evidence:

        if item["product_found"]:
            product_matches += 1

        if item["company_found"]:
            company_matches += 1

        if item["batch_found"]:
            batch_matches += 1

        if item[
            "relevant_information"
        ]:
            useful_sources += 1

    if batch_matches > 0:

        assessment = "Evidence Found"

        confidence = 85.0

        reason = (
            "The submitted batch number was "
            "found in an official source. "
            "This is supporting evidence only "
            "and does not by itself prove "
            "physical authenticity."
        )

    elif (
        product_matches > 0
        and company_matches > 0
    ):

        assessment = "Evidence Found"

        confidence = 65.0

        reason = (
            "The product and company information "
            "were found together in official-source "
            "material. Additional product-level "
            "traceability or physical verification "
            "is required."
        )

    elif useful_sources > 0:

        assessment = "Reference Evidence"

        confidence = 50.0

        reason = (
            "Official agricultural information "
            "relevant to this type of product "
            "was found, but the submitted product "
            "could not be directly authenticated."
        )

    else:

        assessment = "Inconclusive"

        confidence = 30.0

        reason = (
            "No sufficient product-level match "
            "was found in the selected official "
            "sources. This does not prove that "
            "the product is fake."
        )

    return {
        "assessment": assessment,
        "confidence": confidence,
        "reason": reason,
        "product_matches": product_matches,
        "company_matches": company_matches,
        "batch_matches": batch_matches,
        "useful_sources": useful_sources
    }


def research_product(
    product_id,
    product_type,
    product_name,
    company,
    batch_no
):
    evidence = collect_official_evidence(
        product_type,
        product_name,
        company,
        batch_no
    )

    analysis = analyze_research_evidence(
        product_type,
        product_name,
        company,
        batch_no,
        evidence
    )

    return {
        "product_id": product_id,
        "product_type": product_type,
        "product_name": product_name,
        "company": company,
        "batch_no": batch_no,
        "assessment": analysis[
            "assessment"
        ],
        "confidence": analysis[
            "confidence"
        ],
        "reason": analysis[
            "reason"
        ],
        "product_matches": analysis[
            "product_matches"
        ],
        "company_matches": analysis[
            "company_matches"
        ],
        "batch_matches": analysis[
            "batch_matches"
        ],
        "useful_sources": analysis[
            "useful_sources"
        ],
        "evidence": evidence,
        "sources": [
            {
                "name": item["source"],
                "url": item["url"]
            }
            for item in evidence
        ]
    }


def save_research_result(result):
    conn = sqlite3.connect(
        "complaints.db"
    )

    conn.execute("""
        INSERT INTO ai_research_results
        (
            complaint_id,
            product_id,
            product_type,
            product_name,
            company,
            batch_no,
            assessment,
            confidence,
            reason,
            evidence,
            sources,
            analyzed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        result.get("complaint_id"),
        result.get("product_id"),
        result.get("product_type"),
        result.get("product_name"),
        result.get("company"),
        result.get("batch_no"),
        result.get("assessment"),
        result.get("confidence"),
        result.get("reason"),
        json.dumps(
            result.get("evidence", []),
            ensure_ascii=False
        ),
        json.dumps(
            result.get("sources", []),
            ensure_ascii=False
        ),
        datetime.utcnow().isoformat()
    ))

    conn.commit()

    research_id = conn.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    conn.close()

    return research_id


def test_product_research():
    return research_product(
        "FS001",
        "Seed",
        "Paddy Seeds",
        "ABC Seeds",
        "B101"
    )


def test_save_research():
    result = test_product_research()

    research_id = save_research_result(
        result
    )

    return {
        "research_id": research_id,
        "result": result
    }