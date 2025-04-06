import os
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import uvicorn
import google.generativeai as genai
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import re
import json
import time
import asyncio
from pathlib import Path
import firecrawl  # Import the module without specifying a class
from logger import api_logger, scraper_logger, app_logger

# Load environment variables
load_dotenv()
app_logger.info("Environment variables loaded")

# Configure Google Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    app_logger.error("GEMINI_API_KEY not found in environment variables")
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Configure Firecrawl API
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
if not FIRECRAWL_API_KEY:
    app_logger.error("FIRECRAWL_API_KEY not found in environment variables")
    raise ValueError("FIRECRAWL_API_KEY not found in environment variables")

# Initialize Firecrawl client properly
firecrawl_client = firecrawl.FirecrawlApp(api_key=FIRECRAWL_API_KEY)
app_logger.info("Firecrawl API initialized")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')
app_logger.info("Gemini API initialized")

app = FastAPI(title="SHL Assessment Recommender")
app_logger.info("FastAPI application created")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app_logger.info("CORS middleware added")

# Cache file path
CACHE_FILE = Path("shl_assessments_cache.json")
CACHE_EXPIRY = 86400  # Cache expiry in seconds (24 hours)

# Add logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    api_logger.info(
        f"Path: {request.url.path} | "
        f"Method: {request.method} | "
        f"Status: {response.status_code} | "
        f"Processing time: {process_time:.4f}s"
    )
    return response

class QueryInput(BaseModel):
    text: Optional[str] = None
    url: Optional[str] = None

class Assessment(BaseModel):
    name: str
    url: str
    remote_testing: bool
    adaptive_support: bool
    duration: str
    test_type: str

class RecommendationResponse(BaseModel):
    recommendations: List[Assessment]

class SHLAssessmentSchema(BaseModel):
    name: str = Field(description="The name of the assessment product")
    description: Optional[str] = Field(description="Brief description of the assessment")
    remote_testing: bool = Field(description="Whether the assessment supports remote testing")
    adaptive_support: bool = Field(description="Whether the assessment uses adaptive/IRT technology")
    duration: str = Field(description="Duration of the assessment (e.g. '10-15 minutes')")
    test_type: str = Field(description="Type of assessment (e.g. 'Cognitive ability', 'Personality assessment')")

async def scrape_shl_assessments():
    """Scrape SHL assessment data using Firecrawl"""
    
    scraper_logger.info("Starting SHL assessment scraping")
    
    # SHL product pages to scrape
    shl_urls = [
        "https://www.shl.com/solutions/products/", 
    ]
    
    assessments = []
    
    try:
        # First try to scrape the main products page to discover product URLs
        scraper_logger.info("Scraping main product page")
        
        # Use the correct Firecrawl API method
        try:
            main_page_result = await firecrawl_client.scrape_async(
                url="https://www.shl.com/solutions/products/",
                extract_links=True
            )
            
            # Extract product links - adapt to actual API response structure
            links = main_page_result.get("links", [])
            
            # Add product links to our list
            for link in links:
                if isinstance(link, str) and 'products' in link and link not in shl_urls:
                    # Only add links that look like product pages
                    if '/products/' in link and not link.endswith('/products/'):
                        shl_urls.append(link)
            
        except Exception as e:
            scraper_logger.error(f"Error scraping main page: {str(e)}")
            # Fallback: use traditional request if Firecrawl fails
            try:
                response = requests.get("https://www.shl.com/solutions/products/")
                soup = BeautifulSoup(response.text, 'html.parser')
                for a in soup.find_all('a', href=True):
                    link = a['href']
                    if '/products/' in link and not link.endswith('/products/') and link not in shl_urls:
                        # Ensure URL is absolute
                        if not link.startswith('http'):
                            link = 'https://www.shl.com' + link if not link.startswith('/') else 'https://www.shl.com' + link
                        shl_urls.append(link)
            except Exception as e2:
                scraper_logger.error(f"Fallback scraping also failed: {str(e2)}")
        
        scraper_logger.info(f"Found {len(shl_urls)} product URLs to scrape")
        
        # Now scrape each product page
        for url in shl_urls:
            try:
                # Scrape the product page with appropriate method
                scraper_logger.debug(f"Scraping product page: {url}")
                
                try:
                    # Try using Firecrawl
                    result = await firecrawl_client.scrape_async(
                        url=url,
                        extract_text=True,
                        extract_metadata=True
                    )
                    
                    page_text = result.get("text", "")
                    page_title = result.get("metadata", {}).get("title", "")
                    
                except Exception as e:
                    scraper_logger.error(f"Firecrawl error for {url}: {str(e)}")
                    # Fallback to traditional request
                    response = requests.get(url)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    page_text = soup.get_text(separator=' ', strip=True)
                    page_title = soup.title.string if soup.title else ""
                
                # Get product name with improved fallback logic
                name = None
                
                # Try to get from title
                if page_title:
                    # Remove common suffixes from title
                    name = page_title.replace(" | SHL", "").replace("SHL |", "").replace("SHL", "").strip()
                
                # Try to extract from the URL path if still empty
                if not name or name == "":
                    url_parts = url.rstrip('/').split('/')
                    # Get the last non-empty segment of the URL
                    for part in reversed(url_parts):
                        if part and part != "solutions" and part != "products":
                            # Convert slug to readable name
                            product_name = part.replace("-", " ").replace("%20", " ").strip()
                            name = product_name.title()
                            break
                
                # Final fallback: check if the URL indicates a specific product category
                if not name or name == "" or name.lower() in ["home", "solutions", "products", "assessments"]:
                    if "personality" in url.lower():
                        name = "Personality Assessment"
                    elif "cognitive" in url.lower():
                        name = "Cognitive Assessment"
                    elif "skills" in url.lower():
                        name = "Skills Assessment"
                    elif "video-interviews" in url.lower():
                        name = "Video Interview Assessment"
                    elif "360" in url.lower():
                        name = "360 Feedback Assessment"
                    else:
                        # Last resort
                        name = "SHL Assessment"
                        
                scraper_logger.debug(f"Extracted name: '{name}' from URL: {url}")
                
                # Use Gemini to extract structured information about the assessment
                content = page_text
                
                # Use Gemini to analyze the product page content
                prompt = f"""
                Analyze this SHL assessment product page content and extract the following information:
                
                Content: {content}
                
                URL: {url}
                
                Extract:
                1. Remote testing availability (true/false)
                2. Does it use adaptive/IRT technology (true/false)
                3. Duration (e.g., "15-20 minutes")
                4. Test type (e.g., "Cognitive ability", "Personality assessment")
                
                If information is not available, make a reasonable assumption.
                Return response as JSON with keys: remote_testing (boolean), adaptive_support (boolean), duration (string), test_type (string)
                """
                
                response = model.generate_content(prompt)
                
                # Parse the JSON response from Gemini
                try:
                    # Try to extract JSON from the response
                    json_text = re.search(r'({.*})', response.text, re.DOTALL)
                    if json_text:
                        assessment_details = json.loads(json_text.group(1))
                    else:
                        # Fallback if no JSON found
                        assessment_details = {
                            "remote_testing": True,
                            "adaptive_support": False,
                            "duration": "20-30 minutes",
                            "test_type": "Assessment"
                        }
                except Exception as e:
                    # Fallback if JSON parsing fails
                    assessment_details = {
                        "remote_testing": True,
                        "adaptive_support": False,
                        "duration": "20-30 minutes",
                        "test_type": "Assessment"
                    }
                
                # Create the assessment object
                assessment = {
                    "name": name,
                    "url": url,
                    "remote_testing": assessment_details.get("remote_testing", True),
                    "adaptive_support": assessment_details.get("adaptive_support", False),
                    "duration": assessment_details.get("duration", "20-30 minutes"),
                    "test_type": assessment_details.get("test_type", "Assessment")
                }
                
                # Add to our list of assessments
                assessments.append(assessment)
                scraper_logger.debug(f"Added assessment: {name}")
                
            except Exception as e:
                # Log error but continue with other URLs
                scraper_logger.error(f"Error scraping {url}: {str(e)}")
    
    except Exception as e:
        # Log the error but don't fail completely
        scraper_logger.error(f"Error during scraping: {str(e)}")
        
    # Add default assessments if scraping failed completely
    if not assessments:
        scraper_logger.warning("Returning fallback assessment data")
        assessments = [
            {
                "name": "Verify Interactive",
                "url": "https://www.shl.com/solutions/products/verify-interactive/",
                "remote_testing": True,
                "adaptive_support": True,
                "duration": "10-15 minutes",
                "test_type": "Cognitive ability"
            },
            {
                "name": "Occupational Personality Questionnaire (OPQ)",
                "url": "https://www.shl.com/solutions/products/opq-personality-test/",
                "remote_testing": True,
                "adaptive_support": False,
                "duration": "25-40 minutes",
                "test_type": "Personality assessment"
            }
        ]
    
    # Make sure we don't have duplicate URLs and ensure all assessments have valid names
    unique_assessments = []
    seen_urls = set()
    
    for assessment in assessments:
        if assessment["url"] not in seen_urls:
            # Ensure assessment has valid name
            if not assessment["name"] or assessment["name"] == "Unknown Product":
                # Try to derive name from the URL as a fallback
                url_parts = assessment["url"].rstrip('/').split('/')
                for part in reversed(url_parts):
                    if part and part != "solutions" and part != "products" and part not in seen_urls:
                        # Convert slug to readable name
                        product_name = part.replace("-", " ").replace("%20", " ").strip()
                        assessment["name"] = product_name.title()
                        break
                
                # If still no name, assign a default
                if not assessment["name"] or assessment["name"] == "Unknown Product":
                    assessment["name"] = "SHL Assessment - " + assessment["test_type"]
            
            seen_urls.add(assessment["url"])
            unique_assessments.append(assessment)
    
    scraper_logger.info(f"Scraping completed. Found {len(unique_assessments)} unique assessments")
    return unique_assessments

async def fetch_shl_assessments_async():
    """Async version of fetch_shl_assessments that properly handles async operations"""
    
    # Check if cached data exists and is not expired
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                
            # Check if cache is still valid
            timestamp = cache_data.get('timestamp', 0)
            current_time = time.time()
            
            if current_time - timestamp < CACHE_EXPIRY:
                api_logger.info("Using cached assessment data")
                return cache_data.get('assessments', [])
            else:
                api_logger.info("Cache expired, fetching fresh data")
        except Exception as e:
            api_logger.error(f"Error reading cache: {str(e)}")
            # If there's any error reading the cache, ignore and proceed
            pass
    else:
        api_logger.info("No cache found, fetching fresh data")
    
    # If we reach here, we need to scrape fresh data
    # Properly await the async function
    assessments = await scrape_shl_assessments()
    
    # Save to cache
    cache_data = {
        'timestamp': time.time(),
        'assessments': assessments
    }
    
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)
        api_logger.info("Assessment data cached successfully")
    except Exception as e:
        api_logger.error(f"Error writing cache: {str(e)}")
    
    return assessments

def fetch_shl_assessments():
    """Synchronous version to get cached assessments without scraping"""
    
    # If cache exists and is valid, return it
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                
            # Check if cache is still valid
            timestamp = cache_data.get('timestamp', 0)
            current_time = time.time()
            
            if current_time - timestamp < CACHE_EXPIRY:
                api_logger.info("Using cached assessment data")
                return cache_data.get('assessments', [])
        except Exception as e:
            api_logger.error(f"Error reading cache: {str(e)}")
    
    # If no valid cache, return a minimal default set
    api_logger.warning("No valid cache found, returning default assessments")
    return [
        {
            "name": "Verify Interactive",
            "url": "https://www.shl.com/solutions/products/verify-interactive/",
            "remote_testing": True,
            "adaptive_support": True,
            "duration": "10-15 minutes",
            "test_type": "Cognitive ability"
        },
        {
            "name": "Occupational Personality Questionnaire (OPQ)",
            "url": "https://www.shl.com/solutions/products/opq-personality-test/",
            "remote_testing": True,
            "adaptive_support": False,
            "duration": "25-40 minutes",
            "test_type": "Personality assessment"
        }
    ]

@app.post("/recommend", response_model=RecommendationResponse)
async def recommend_assessments(query: QueryInput):
    api_logger.info(f"Recommendation request received: {query.text[:50] if query.text else 'No text'}, URL: {query.url if query.url else 'No URL'}")
    
    if not query.text and not query.url:
        api_logger.warning("Request missing both text and URL")
        raise HTTPException(status_code=400, detail="Either text or URL must be provided")
    
    # If URL is provided, extract text from the webpage
    if query.url:
        try:
            # Use Firecrawl to extract text from the URL
            try:
                result = await firecrawl_client.scrape_async(
                    url=query.url,
                    extract_text=True
                )
                query_text = result.get("text", "")
            except Exception as e:
                api_logger.error(f"Firecrawl error: {str(e)}")
                query_text = ""
                
            if not query_text:
                # Fallback to traditional method if Firecrawl fails to extract text
                response = requests.get(query.url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract text from the webpage (remove scripts, styles, etc.)
                for script in soup(["script", "style"]):
                    script.extract()
                
                query_text = soup.get_text(separator=' ', strip=True)
        except Exception as e:
            api_logger.error(f"Failed to fetch or parse URL: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Failed to fetch or parse URL: {str(e)}")
    else:
        query_text = query.text
    
    # Generate recommendations using Gemini
    recommendations = await get_recommendations_async(query_text)
    
    api_logger.info(f"Returning {len(recommendations)} recommendations")
    return RecommendationResponse(recommendations=recommendations)

async def get_recommendations_async(query_text: str) -> List[Assessment]:
    # Fetch the assessment data
    assessments_data = await fetch_shl_assessments_async()
    
    # Prompt for Gemini to analyze the job description and recommend assessments
    prompt = f"""
    You are an assessment recommendation system for SHL. Based on the following job description or query, 
    recommend the most relevant assessments from SHL's catalog.
    
    Here is the job description or query:
    {query_text}
    
    Analyze the skills, experience, and requirements mentioned in the text. 
    Select at most 10 most relevant assessments from the SHL product catalog.
    Return your answer as a list of assessment IDs ONLY, nothing else.
    Choose from the following assessment IDs: {", ".join([str(i) for i in range(len(assessments_data))])}
    
    SHL Assessment List:
    {json.dumps([{"id": i, "name": assessment["name"], "type": assessment["test_type"]} for i, assessment in enumerate(assessments_data)])}
    """
    
    # Get recommendations from Gemini
    try:
        response = model.generate_content(prompt)
        api_logger.debug("Received response from Gemini")
    except Exception as e:
        api_logger.error(f"Error getting recommendations from Gemini: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI model error: {str(e)}")
    
    # Extract assessment IDs from the response
    ids_text = response.text
    ids = re.findall(r'\d+', ids_text)
    
    # Convert to integers and remove duplicates
    try:
        unique_ids = list(set([int(id) for id in ids]))[:10]  # Limit to 10 recommendations
    except ValueError:
        api_logger.error("Failed to parse Gemini response")
        raise HTTPException(status_code=500, detail="Failed to parse Gemini response")
    
    # Fetch assessment details
    recommendations = []
    for id in unique_ids:
        if 0 <= id < len(assessments_data):
            assessment = assessments_data[id]
            recommendations.append(Assessment(
                name=assessment["name"],
                url=assessment["url"],
                remote_testing=assessment["remote_testing"],
                adaptive_support=assessment["adaptive_support"],
                duration=assessment["duration"],
                test_type=assessment["test_type"]
            ))
    
    api_logger.info(f"Generated {len(recommendations)} recommendations")
    return recommendations

@app.get("/health")
async def health_check():
    api_logger.debug("Health check request")
    return {"status": "healthy"}

@app.get("/assessments")
async def get_assessments():
    """Endpoint to get all available assessments"""
    api_logger.info("Request for all assessments")
    
    # Use the async version to properly handle async operations
    assessments = await fetch_shl_assessments_async()
    return {"assessments": assessments}

@app.get("/refresh-assessments")
async def refresh_assessments(background_tasks: BackgroundTasks):
    """Force refresh the assessment data"""
    api_logger.info("Request to refresh assessment data")
    
    # Clear the cache by deleting the file
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
        api_logger.info("Deleted existing cache file")
    
    # Fetch fresh assessment data (async-aware)
    assessments = await scrape_shl_assessments()
    
    # Check for unnamed assessments
    unnamed_count = sum(1 for assessment in assessments if assessment["name"] == "Unknown Product")
    if unnamed_count > 0:
        api_logger.warning(f"Found {unnamed_count} assessments with 'Unknown Product' as name")
    
    # Save to cache
    cache_data = {
        'timestamp': time.time(),
        'assessments': assessments
    }
    
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache_data, f)
    
    # Start a background task to fix unnamed products in case there are any
    if unnamed_count > 0:
        background_tasks.add_task(fix_assessment_names)
    
    api_logger.info(f"Assessment data refreshed: {len(assessments)} assessments cached")
    return {"status": "success", "count": len(assessments), "unnamed_count": unnamed_count}

def fix_assessment_names():
    """Utility to fix unnamed assessments in the cache file"""
    cache_file = CACHE_FILE
    
    if not cache_file.exists():
        app_logger.warning("Cache file not found for fixing names")
        return
    
    # Load the existing cache
    with open(cache_file, 'r') as f:
        cache_data = json.load(f)
    
    assessments = cache_data.get('assessments', [])
    unnamed_count = sum(1 for a in assessments if a.get("name") == "Unknown Product")
    app_logger.info(f"Found {unnamed_count} assessments with 'Unknown Product' as name")
    
    # Process each assessment
    for assessment in assessments:
        if assessment.get("name") == "Unknown Product":
            url = assessment.get("url", "")
            
            # Try to extract name from URL
            url_parts = url.rstrip('/').split('/')
            
            # Get the last meaningful part of the URL
            name = None
            for part in reversed(url_parts):
                if part and part not in ["", "solutions", "products", "assessments", "view"]:
                    # Convert slug to readable name
                    product_name = part.replace("-", " ").replace("%20", " ")
                    # Clean up special characters and normalize spaces
                    product_name = re.sub(r'[^\w\s]', ' ', product_name)
                    product_name = re.sub(r'\s+', ' ', product_name).strip()
                    name = product_name.title()
                    break
            
            # Apply specific naming rules
            if "personality" in url.lower():
                name = name or "Personality Assessment"
            elif "cognitive" in url.lower():
                name = name or "Cognitive Assessment"
            elif "video-interview" in url.lower():
                name = name or "Video Interview"
            elif "360" in url.lower():
                name = name or "360 Feedback Assessment"
            
            # Final fallback
            name = name or f"SHL Assessment - {assessment.get('test_type', 'General')}"
            
            app_logger.info(f"Renamed: 'Unknown Product' → '{name}' for URL: {url}")
            assessment["name"] = name
    
    # Save the updated cache
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f)
    
    fixed_count = unnamed_count - sum(1 for a in assessments if a.get("name") == "Unknown Product")
    app_logger.info(f"Fixed {fixed_count} assessment names. Cache file updated.")

if __name__ == "__main__":
    app_logger.info("Starting FastAPI server")
    # uvicorn.run("main:app", host="localhost", port=8000, reload=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)
