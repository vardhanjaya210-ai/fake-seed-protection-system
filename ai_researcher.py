import os
import json
import re
import sqlite3
import time
import requests

from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

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

    url = str(url).strip()

    match = re.search(
        r"https?://[^\s\]\)\"']+",
        url
    )

    if match:
        return match.group(0).rstrip(".,;")

    return url


def clean_sentence(text):
    if not text:
        return ""

    text = re.sub(
        r"\s+",
        " ",
        str(text)
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

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def fetch_webpage(url):
    try:
        url = clean_url(url)

        if not url:
            return ""

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

        main_content = soup.find("main")

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

        return clean_sentence(text)

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

    return [
        clean_sentence(sentence)
        for sentence in sentences
        if len(clean_sentence(sentence)) >= 40
    ]


def find_relevant_sentences(
    text,
    product_name,
    company,
    batch_no
):
    if not text:
        return []

    sentences = split_into_sentences(text)

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

    matches = []

    for sentence in sentences:

        lower_sentence = sentence.lower()

        score = sum(
            1
            for term in search_terms
            if term and term in lower_sentence
        )

        if score > 0:
            matches.append(
                (score, sentence)
            )

    matches.sort(
        key=lambda x: x[0],
        reverse=True
    )

    result = []
    seen = set()

    for _, sentence in matches:

        key = sentence.lower()

        if key in seen:
            continue

        seen.add(key)

        result.append(
            sentence[:500]
        )

        if len(result) >= 3:
            break

    return result


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
            "The submitted product and company information were found in the official source."
        )

    elif product_found:

        evidence.append(
            "The submitted product name was found in the official source."
        )

    elif company_found:

        evidence.append(
            "The submitted company name was found in the official source."
        )

    for sentence in relevant_sentences:

        sentence = clean_sentence(
            sentence
        )

        if sentence and sentence not in evidence:

            evidence.append(
                sentence[:500]
            )

        if len(evidence) >= 3:
            break

    if not evidence:

        evidence.append(
            "The official source contains agricultural information relevant to product verification, but no direct product-level match was found."
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
    product_matches = sum(
        1
        for item in evidence
        if item.get("product_found")
    )

    company_matches = sum(
        1
        for item in evidence
        if item.get("company_found")
    )

    batch_matches = sum(
        1
        for item in evidence
        if item.get("batch_found")
    )

    useful_sources = sum(
        1
        for item in evidence
        if item.get("relevant_information")
    )

    if batch_matches > 0:

        assessment = "Evidence Found"
        confidence = 85.0

        reason = (
            "The submitted batch number was found "
            "in an official source. This is supporting "
            "evidence only and does not by itself prove "
            "physical authenticity."
        )

    elif (
        product_matches > 0
        and company_matches > 0
    ):

        assessment = "Evidence Found"
        confidence = 65.0

        reason = (
            "The submitted product and company information "
            "were found in official-source material. "
            "Additional verification is required."
        )

    elif useful_sources > 0:

        assessment = "Reference Evidence"
        confidence = 50.0

        reason = (
            "Official agricultural information relevant "
            "to this product type was found, but the "
            "submitted product could not be directly authenticated."
        )

    else:

        assessment = "Inconclusive"
        confidence = 30.0

        reason = (
            "No sufficient product-level match was found "
            "in the selected official sources. This does "
            "not prove that the product is fake."
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


def prepare_groq_evidence(official_evidence):
    result = []

    for item in official_evidence[:3]:

        info = item.get(
            "relevant_information",
            []
        )

        if not isinstance(info, list):
            info = [str(info)]

        info = [
            clean_sentence(x)[:350]
            for x in info[:1]
            if x
        ]

        result.append({
            "source": str(
                item.get(
                    "source",
                    ""
                )
            )[:120],
            "url": clean_url(
                item.get(
                    "url",
                    ""
                )
            ),
            "product_found": bool(
                item.get(
                    "product_found",
                    False
                )
            ),
            "company_found": bool(
                item.get(
                    "company_found",
                    False
                )
            ),
            "batch_found": bool(
                item.get(
                    "batch_found",
                    False
                )
            ),
            "info": info
        })

    return result


def get_retry_delay(error, attempt):
    message = str(error)

    match = re.search(
        r"try again in\s+([0-9.]+)s",
        message,
        flags=re.IGNORECASE
    )

    if match:

        try:

            delay = float(
                match.group(1)
            )

            return min(
                max(
                    delay + 0.2,
                    1.0
                ),
                15.0
            )

        except ValueError:
            pass

    return min(
        2 ** attempt,
        10
    )


def is_rate_limit_error(error):
    message = str(error).lower()

    return (
        "429" in message
        or "rate limit" in message
        or "rate_limit_exceeded" in message
        or "tokens per minute" in message
    )


def groq_research(
    product_id,
    product_type,
    product_name,
    company,
    batch_no,
    description,
    official_evidence
):
    api_key = os.environ.get(
        "GROQ_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY was not found. Check your .env file."
        )

    client = Groq(
        api_key=api_key,
        default_headers={
            "Groq-Model-Version": "latest"
        }
    )

    compact_evidence = prepare_groq_evidence(
        official_evidence
    )

    evidence_text = json.dumps(
        compact_evidence,
        ensure_ascii=False,
        separators=(",", ":")
    )

    product_id = str(
        product_id or ""
    )[:80]

    product_type = str(
        product_type or ""
    )[:60]

    product_name = str(
        product_name or ""
    )[:120]

    company = str(
        company or ""
    )[:120]

    batch_no = str(
        batch_no or ""
    )[:80]

    description = clean_sentence(
        description
    )[:700]

    prompt = f"""
Analyze this agricultural product complaint.

Do not claim the physical product is definitely fake or genuine.
Give a preliminary evidence-based assessment.

Use web search when useful. Prefer official government,
certification, laboratory, manufacturer and reliable sources.

Product ID: {product_id}
Type: {product_type}
Product: {product_name}
Company: {company}
Batch: {batch_no}

Farmer complaint:
{description}

Existing official evidence:
{evidence_text}

Return ONLY JSON with:

{{
"assessment":"Low Risk | Possible Risk | High Risk | Inconclusive | Reference Evidence | Evidence Found",
"confidence":0,
"reason":"short explanation",
"ai_finding":"what the AI found from the complaint, submitted details, official evidence and web research",
"complaint_analysis":"what the farmer complaint indicates",
"product_information":"supported product information",
"recommended_action":"practical next step",
"evidence":["important evidence"],
"sources":[{{"name":"source name","url":"source url"}}]
}}

Important:
- Do not invent information.
- Clearly distinguish evidence from the farmer's complaint.
- General information is not proof of authenticity.
- If authentication is not possible, say so.
- Use simple farmer-friendly language.
"""

    last_error = None

    for attempt in range(3):

        try:

            response = client.chat.completions.create(
                model="groq/compound-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a careful agricultural research "
                            "assistant. Research current information when "
                            "needed. Prefer reliable official sources. "
                            "Never invent facts or claim physical "
                            "authenticity with certainty."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                compound_custom={
                    "tools": {
                        "enabled_tools": [
                            "web_search",
                            "visit_website"
                        ]
                    }
                },
                response_format={
                    "type": "json_object"
                }
            )

            content = (
                response
                .choices[0]
                .message
                .content
            )

            if not content:
                raise RuntimeError(
                    "Groq returned an empty response."
                )

            content = content.strip()

            content = re.sub(
                r"^```json\s*",
                "",
                content,
                flags=re.IGNORECASE
            )

            content = re.sub(
                r"\s*```$",
                "",
                content
            )

            result = json.loads(
                content
            )

            if not isinstance(
                result,
                dict
            ):
                raise RuntimeError(
                    "Groq returned an unexpected response."
                )

            result.setdefault(
                "assessment",
                "Inconclusive"
            )

            result.setdefault(
                "confidence",
                0
            )

            result.setdefault(
                "reason",
                "The AI could not produce a sufficient assessment."
            )

            result.setdefault(
                "ai_finding",
                ""
            )

            result.setdefault(
                "complaint_analysis",
                ""
            )

            result.setdefault(
                "product_information",
                ""
            )

            result.setdefault(
                "recommended_action",
                "Consult an agricultural authority or laboratory for further verification."
            )

            result.setdefault(
                "evidence",
                []
            )

            result.setdefault(
                "sources",
                []
            )

            if not isinstance(
                result["evidence"],
                list
            ):
                result["evidence"] = [
                    str(
                        result["evidence"]
                    )
                ]

            if not isinstance(
                result["sources"],
                list
            ):
                result["sources"] = []

            return result

        except Exception as error:

            last_error = error

            if not is_rate_limit_error(
                error
            ):
                raise

            if attempt >= 2:
                break

            delay = get_retry_delay(
                error,
                attempt + 1
            )

            print(
                f"Groq rate limit reached. "
                f"Retrying in {delay:.1f} seconds..."
            )

            time.sleep(
                delay
            )

    raise RuntimeError(
        "Groq request failed after 3 attempts: "
        + str(last_error)
    )


def research_product(
    product_id,
    product_type,
    product_name,
    company,
    batch_no,
    description=""
):
    official_evidence = collect_official_evidence(
        product_type,
        product_name,
        company,
        batch_no
    )

    basic_analysis = analyze_research_evidence(
        product_type,
        product_name,
        company,
        batch_no,
        official_evidence
    )

    try:

        ai_result = groq_research(
            product_id,
            product_type,
            product_name,
            company,
            batch_no,
            description,
            official_evidence
        )

    except Exception as error:

        print(
            "Groq research error:",
            error
        )

        ai_result = {
            "assessment": basic_analysis[
                "assessment"
            ],
            "confidence": basic_analysis[
                "confidence"
            ],
            "reason": basic_analysis[
                "reason"
            ],
            "ai_finding": (
                "The reported problem was analyzed "
                "using the available official agricultural "
                "information, but the AI web research service "
                "was unavailable. Direct authentication of "
                "the submitted product was therefore not established."
            ),
            "complaint_analysis": (
                "The farmer reported a product-related concern. "
                "The complaint should be considered a possible "
                "quality or product verification concern until "
                "further evidence is obtained."
            ),
            "product_information": (
                "The farmer submitted product information "
                "including the product name, company and batch number."
            ),
            "recommended_action": (
                "Keep the product packet and purchase bill "
                "and consult the appropriate agricultural authority, "
                "certification agency or laboratory for further verification."
            ),
            "evidence": [],
            "sources": []
        }

    combined_evidence = []

    for item in official_evidence:

        for information in item.get(
            "relevant_information",
            []
        ):

            information = clean_sentence(
                information
            )

            if (
                information
                and information not in combined_evidence
            ):

                combined_evidence.append(
                    information
                )

    for item in ai_result.get(
        "evidence",
        []
    ):

        if isinstance(
            item,
            dict
        ):

            text = (
                item.get("text")
                or item.get("evidence")
                or item.get("description")
                or ""
            )

        else:

            text = str(item)

        text = clean_sentence(
            text
        )

        if (
            text
            and text not in combined_evidence
        ):

            combined_evidence.append(
                text
            )

    sources = []

    for item in official_evidence:

        source = {
            "name": item["source"],
            "url": item["url"]
        }

        if source not in sources:
            sources.append(source)

    for source in ai_result.get(
        "sources",
        []
    ):

        if not isinstance(
            source,
            dict
        ):
            continue

        name = str(
            source.get(
                "name",
                ""
            )
        ).strip()

        url = clean_url(
            source.get(
                "url",
                ""
            )
        )

        if name and url:

            clean_source = {
                "name": name,
                "url": url
            }

            if clean_source not in sources:

                sources.append(
                    clean_source
                )

    try:

        confidence = float(
            ai_result.get(
                "confidence",
                basic_analysis["confidence"]
            )
        )

    except (
        TypeError,
        ValueError
    ):

        confidence = basic_analysis[
            "confidence"
        ]

    confidence = max(
        0.0,
        min(
            confidence,
            100.0
        )
    )

    ai_finding = str(
        ai_result.get(
            "ai_finding",
            ""
        )
    ).strip()

    if not ai_finding:

        ai_finding = (
            "The AI analyzed the complaint and available "
            "agricultural information but could not produce "
            "a detailed finding."
        )

    complaint_analysis = str(
        ai_result.get(
            "complaint_analysis",
            ""
        )
    ).strip()

    if not complaint_analysis:

        complaint_analysis = (
            "The complaint indicates a possible product "
            "quality or verification concern."
        )

    product_information = str(
        ai_result.get(
            "product_information",
            ""
        )
    ).strip()

    if not product_information:

        product_information = (
            "The submitted product information was "
            "considered during the analysis."
        )

    recommended_action = str(
        ai_result.get(
            "recommended_action",
            ""
        )
    ).strip()

    if not recommended_action:

        recommended_action = (
            "Consult an agricultural expert or appropriate "
            "authority for further verification."
        )

    return {
        "product_id": product_id,
        "product_type": product_type,
        "product_name": product_name,
        "company": company,
        "batch_no": batch_no,
        "assessment": ai_result.get(
            "assessment",
            basic_analysis["assessment"]
        ),
        "confidence": confidence,
        "reason": ai_result.get(
            "reason",
            basic_analysis["reason"]
        ),
        "ai_finding": ai_finding,
        "product_matches": basic_analysis[
            "product_matches"
        ],
        "company_matches": basic_analysis[
            "company_matches"
        ],
        "batch_matches": basic_analysis[
            "batch_matches"
        ],
        "useful_sources": basic_analysis[
            "useful_sources"
        ],
        "evidence": combined_evidence,
        "product_information": product_information,
        "complaint_analysis": complaint_analysis,
        "recommended_action": recommended_action,
        "official_evidence": official_evidence,
        "sources": sources,
        "analyzed_at": datetime.utcnow().isoformat()
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
            result.get(
                "evidence",
                []
            ),
            ensure_ascii=False
        ),
        json.dumps(
            result.get(
                "sources",
                []
            ),
            ensure_ascii=False
        ),
        result.get(
            "analyzed_at",
            datetime.utcnow().isoformat()
        )
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
        "B101",
        "The farmer reports poor germination and suspects that the product may be low quality."
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