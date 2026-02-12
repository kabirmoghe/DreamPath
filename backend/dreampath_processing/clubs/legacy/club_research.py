# FOR TOOLS
import os
import asyncio
import requests
from dotenv import load_dotenv
from serpapi import GoogleSearch # type: ignore
from ratelimit import limits, sleep_and_retry # type: ignore
import aiohttp
from readability import Document # type: ignore
from bs4 import BeautifulSoup
import json
from dreampath_processing.clubs.prompts.club_matching_prompts import EXTRACT_CLUB_INFO_PROMPT
from urllib.parse import urlparse, urljoin

# FOR AGENT
from langchain.agents import Tool, AgentExecutor, create_react_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain import hub

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# -- DEFINING ASYNC RESEARCH FUNCTIONS --

# Limit to 5 calls per second (SerpAPI free tier ≈ 5 QPS)
CALLS = 5
TIME_WINDOW = 1

@sleep_and_retry
@limits(calls=CALLS, period=TIME_WINDOW)
def _serpapi_query(params):
    return GoogleSearch(params).get_dict()

async def search_club(club_name, top_k=5):
    """Return the top_k URLs for ‘Dartmouth undergraduate club {club_name}’."""
    query = f'Dartmouth undergraduate club {club_name}'  
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": top_k,
    }
    # offload to threadpool so we don't block the event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _serpapi_query, params)
    return [r["link"] for r in result.get("organic_results", [])]

async def fetch_page(url: str, timeout: int = 10) -> str:
    """
    Fetch URL, strip boilerplate, return main text.
    On any error (download, decode, parse), returns "".
    """
    # 1) Download HTML
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                html = await resp.text()
    except Exception as e:
        # You can swap print for logging if you prefer
        print(f"[fetch_page] download error for {url!r}: {e}")
        return ""

    # 2) Parse & clean
    try:
        soup = BeautifulSoup(html, "lxml")
        body = soup.body or soup  # fallback if <body> is missing

        # Remove unwanted tags
        for tag in body.find_all(["script", "style", "header", "footer", "aside", "nav"]):
            tag.decompose()
    except Exception as e:
        print(f"[fetch_page] parse error for {url!r}: {e}")
        return ""

    # 3) Extract text
    try:
        raw_text = body.get_text(separator="\n")
        # Collapse multiple blank lines & strip whitespace
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        return "\n\n".join(lines)
    except Exception as e:
        print(f"[fetch_page] text-extract error for {url!r}: {e}")
        return ""

async def research_club_batch(club_name, urls, max_urls=3):
    """Process a batch of URLs and return concatenated content"""
    document_text = ""
    
    for i, url in enumerate(urls[:max_urls]):
        try:
            print(f"Fetching page '{url}' [doc. #{i+1}]")
            
            # Fetch main page and internal links concurrently
            page_task = fetch_page(url)
            links_task = extract_links(url, club_name) if document_text else None
            
            page_text = await page_task
            
            if page_text:
                page_text_plus_internal_link_text = page_text
                
                if links_task:  # Only for non-first pages
                    internal_links = await links_task
                    
                    # Fetch all internal links concurrently
                    if internal_links:
                        internal_tasks = [fetch_page(link) for link in internal_links]
                        internal_texts = await asyncio.gather(*internal_tasks, return_exceptions=True)
                        
                        for internal_text in internal_texts[:5]:
                            if isinstance(internal_text, str) and internal_text:
                                print(f"Fetched internal link [for doc. #{i+1}]")
                                page_text_plus_internal_link_text += "\n\n" + "="*30 + "\n\n" + internal_text
                
                document_text = document_text + "\n\n" + "="*30 + "\n\n" + page_text_plus_internal_link_text
            else:
                document_text = page_text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            continue
    
    return document_text

def concat_text(payload):
    """
    Input: a JSON string with {"old_text": <existing document_text>, "new_text": <new page or embedded text>}
    Output: the single string which is old_text + "\n\n" + new_text
    """
    try:
        data = json.loads(payload)
        old = data.get("old_text", "").strip()
        new = data.get("new_text", "").strip()
    except Exception:
        return ""  # fallback to empty if parsing fails

    if not old:
        return new
    # join with a blank‐line separator
    return old + "\n\n" + new


def evaluate_content(text):
    """
    If the text has > 200 tokens, return "ENOUGH"; otherwise "NEED_MORE".
    (You can replace this with an LLM call if you want more nuanced checks.)
    """
    if len(text.split()) > 200:
        return "ENOUGH"
    return "NEED_MORE"

async def extract_links(url, club_name, timeout=5):
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                html = await resp.text()
    except Exception as e:
        print(f"[extract_links] DOWNLOAD ERROR for {url}: {e}")
        return []

    try:
        soup = BeautifulSoup(html, "lxml")
        found_urls = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Build absolute URL
            abs_url = urljoin(url, href)
            parsed = urlparse(abs_url)

            lower_href = abs_url.lower()
            found_urls.add(abs_url)
        return list(found_urls)
    except Exception as e:
        print(f"[extract_links] PARSE ERROR for {url}: {e}")
        return []

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)  # Use ChatOpenAI instead
_prompt = PromptTemplate(
    input_variables=["club_name", "document_text"],
    template=EXTRACT_CLUB_INFO_PROMPT
)
_extract_chain = _prompt | _llm  # Use RunnableSequence instead of LLMChain


def extract_club_info(club_name, document_text):
    """
    Given:
      - club_name: abbreviated/informal name (e.g. "DCG")
      - document_text: concatenated, enumerated page texts (string)

    Returns a Python dict with extracted fields (name, contact_email, description), or None if JSON parsing fails.
    """
    try:
        raw_output = _extract_chain.invoke({
            "club_name": club_name,
            "document_text": document_text
        }).content.strip()
    except Exception as e:
        print(f"[extract_club_info] LLM call failed for '{club_name}': {e}")
        return None

    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError as e:
        print(f"[extract_club_info] JSON parse error for '{club_name}': {e}")
        print("Raw output was:")
        print(raw_output)
        return None

    return parsed


# ───────────────────────────────────────────────────────────────────────────────
# 8) Sync wrappers for async tools (so LangChain can call them synchronously)
# ───────────────────────────────────────────────────────────────────────────────
def sync_search_club(club_name):
    """
    Calls `search_club` and returns a JSON‐encoded string of the URL list.
    """
    try:
        urls = asyncio.get_event_loop().run_until_complete(search_club(club_name, top_k=9))
    except RuntimeError:
        # If no event loop is running, create a new one
        loop = asyncio.new_event_loop()
        urls = loop.run_until_complete(search_club(club_name, top_k=9))
        loop.close()

    return json.dumps(urls)

# def sync_fetch_page(url):
#     """
#     Calls `fetch_page` and returns the raw text (or "" on failure).
#     """
#     try:
#         txt = asyncio.get_event_loop().run_until_complete(fetch_page(url))
#     except RuntimeError:
#         loop = asyncio.new_event_loop()
#         txt = loop.run_until_complete(fetch_page(url))
#         loop.close()
#     return txt


# def sync_extract_links(payload):
#     """
#     Expects payload to be a JSON string: {"url": "<some url>", "club_name": "<club_name>"}.
#     Returns a JSON‐encoded list of new URLs (or [] on failure).
#     """
#     try:
#         data = json.loads(payload)
#         url = data.get("url", "")
#         club_name = data.get("club_name", "")
#     except Exception:
#         return json.dumps([])

#     try:
#         found = asyncio.get_event_loop().run_until_complete(extract_links(url, club_name))
#     except RuntimeError:
#         loop = asyncio.new_event_loop()
#         found = loop.run_until_complete(extract_links(url, club_name))
#         loop.close()

#     return json.dumps(found)

def sync_research_club_batch(payload):
    """Sync wrapper for batch processing"""
    try:
        data = json.loads(payload)
        club_name = data.get("club_name", "")
        urls = data.get("urls", [])
        max_urls = data.get("max_urls", 3)
    except Exception:
        return "EXTRACTION_FAILED (malformed payload)"
    
    try:
        result = asyncio.get_event_loop().run_until_complete(
            research_club_batch(club_name, urls, max_urls)
        )
    except RuntimeError:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(research_club_batch(club_name, urls, max_urls))
        loop.close()
    
    return result

def sync_evaluate_content(text):
    """
    Directly returns "ENOUGH" or "NEED_MORE".
    """
    return evaluate_content(text)

def sync_extract_club_info(payload):
    """
    Expects payload to be a JSON string: {"club_name": "<club_name>", "document_text": "<all text>"}.
    Returns the LLM‐extracted JSON string or "EXTRACTION_FAILED".
    """
    try:
        data = json.loads(payload)
        club_nm = data.get("club_name", "")
        doc_txt = data.get("document_text", "")
    except Exception:
        return "EXTRACTION_FAILED (malformed payload)"

    result = extract_club_info(club_nm, doc_txt)
    if result is None:
        return "EXTRACTION_FAILED (LLM call failed)"
    return json.dumps(result)

def clean_llm_json_output(raw_output):
    """
    Clean LLM output that might contain markdown code blocks or extra formatting.
    """
    # Remove markdown code blocks
    if "```json" in raw_output:
        # Extract content between ```json and ```
        start = raw_output.find("```json") + 7
        end = raw_output.find("```", start)
        if end != -1:
            raw_output = raw_output[start:end].strip()
    elif "```" in raw_output:
        # Handle cases where it's just ``` without json
        start = raw_output.find("```") + 3
        end = raw_output.find("```", start)
        if end != -1:
            raw_output = raw_output[start:end].strip()
    
    return raw_output.strip()

# ───────────────────────────────────────────────────────────────────────────────
# 9) Build LangChain Tools
# ───────────────────────────────────────────────────────────────────────────────
search_tool = Tool(
    name="search_club",
    func=sync_search_club,
    description=(
        "Given a club_name, returns a JSON‐encoded list of up to 9 Dartmouth URLs "
    ),
)

# fetch_tool = Tool(
#     name="fetch_page",
#     func=sync_fetch_page,
#     description=(
#         "Given a single URL, returns the cleaned text of the <body> (all visible text, stripped of boilerplate)."
#     ),
# )

# extract_links_tool = Tool(
#     name="extract_links",
#     func=sync_extract_links,
#     description=(
#         "Given a JSON payload {'url': <URL>, 'club_name': <club_name>}, "
#         "returns a JSON‐encoded list of internal club-related links "
#     ),
# )

concat_tool = Tool(
    name="concat_text",
    func=concat_text,
    description=(
        "Given a JSON payload {'old_text': <string>, 'new_text': <string>}, "
        "returns a single string equal to old_text, followed by two newlines, then new_text."
    ),
)

evaluate_tool = Tool(
    name="evaluate_content",
    func=sync_evaluate_content,
    description=(
        "Given a block of text, returns exactly either 'ENOUGH' or 'NEED_MORE' "
        "based on a simple token-count heuristic."
    ),
)

extract_tool = Tool(
    name="extract_club_info",
    func=sync_extract_club_info,
    description=(
        "Given a JSON payload {'club_name': <club_name>, 'document_text': <all scraped text>}, "
        "returns a JSON string of normalized club metadata "
        "(fields: name, contact_email, description), "
        "or returns 'EXTRACTION_FAILED' if parsing fails."
    ),
)

# Add this as a new tool
batch_tool = Tool(
    name="research_club_batch",
    func=sync_research_club_batch,
    description=(
        "Given a JSON payload {'club_name': <name>, 'urls': [list of urls], 'max_urls': 3}, "
        "fetches and concatenates content from up to max_urls URLs."
    ),
)

TOOLS = [search_tool, concat_tool, evaluate_tool, extract_tool, batch_tool]#, fetch_tool, extract_links_tool]

# Simplified agent prompt that focuses on one step at a time
AGENT_PROMPT = PromptTemplate.from_template("""
You are a Dartmouth Club Research Agent. Your task is to gather information for the club "{club_name}".

Tools: {tools}

Format:
Question: the input question
Thought: what to do next
Action: tool name from [{tool_names}]
Action Input: tool input
Observation: tool result
... (repeat as needed)
Thought: I have the final answer
Final Answer: the result

Process:
1. Use search_club to get URLs
2. Use research_club_batch to fetch content from first 3 URLs
3. Use evaluate_content to check if sufficient
4. If not enough, try more URLs for additional content
5. Use extract_club_info when you have enough content
6. Return the JSON result

Question: Research and extract information for the club: {club_name}
{agent_scratchpad}
""")

# ───────────────────────────────────────────────────────────────────────────────
# 10) Create the Agent
# ───────────────────────────────────────────────────────────────────────────────

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Create agent using the modern approach
agent = create_react_agent(llm, TOOLS, AGENT_PROMPT)

executor = AgentExecutor(
    agent=agent,
    tools=TOOLS,
    verbose=True,
    handle_parsing_errors=True,
)

if __name__ == "__main__":
    CLUB_LIST = [
        # "DIPP",                   
        # "DALI Lab",              
        # "Dartmouth Consulting Group",
        # "DartMUN",
        # "Mock Trial Society",
        # "Debate Team",
        # "Dartmouth Humanitarian Engineering",
        "HackDartmouth"
    ]

    aggregated_club_json = {}

    for club_name in CLUB_LIST:
        print("\n" + "=" * 60)
        print(f"LAUNCHING AGENT FOR CLUB: {club_name}\n")
        try:
            # Use invoke instead of run
            result = executor.invoke({"club_name": club_name})
            final_json_raw = result["output"]
            
            # Clean the output to remove markdown formatting
            cleaned_output = clean_llm_json_output(final_json_raw)
            
            # Try to parse as JSON to ensure it's valid
            try:
                final_json_obj = json.loads(cleaned_output)
                aggregated_club_json[club_name] = final_json_obj
            except json.JSONDecodeError:
                print(f"Failed to parse JSON for {club_name}, storing raw output")
                aggregated_club_json[club_name] = cleaned_output

        except Exception as e:
            print(f"Agent failed for '{club_name}': {e}")
            continue

        print("\nFinal JSON Output for", club_name, ":\n")
        print(json.dumps(aggregated_club_json[club_name], indent=2))
        print("\n" + "=" * 60 + "\n")

    # Write to file with proper formatting
    with open("aggregated_club_json.json", "w") as f:
        json.dump(aggregated_club_json, f, indent=2)
    
