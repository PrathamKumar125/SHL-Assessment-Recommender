# SHL Assessment Recommender

A web application that recommends SHL assessments based on job descriptions. It uses AI to analyze job requirements and match them with appropriate SHL assessment tools.

## Features

- **Job Description Analysis**: Enter job descriptions directly or provide a URL to a job posting
- **AI-Powered Recommendations**: Uses Google's Gemini AI to analyze requirements and recommend relevant assessments
- **Web Scraping**: Automatically collects up-to-date information about SHL's assessment products
- **REST API**: Backend API for integration with other systems
- **User-Friendly Interface**: Simple Gradio interface for easy interaction

## Technology Stack

- **Backend**: FastAPI, Python
- **Frontend**: Gradio
- **AI**: Google Gemini AI
- **Web Scraping**: Firecrawl, BeautifulSoup
- **Containerization**: Docker

## Prerequisites

- Python 3.11+
- Google Gemini API key
- Firecrawl API key

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```
GEMINI_API_KEY=your_gemini_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key
API_URL=http://localhost:8000
```

## Installation

### Local Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd SHL-Assessment-Recommender
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python main.py
   ```
   In a separate terminal:
   ```
   python app.py
   ```

### Docker Installation

1. Build and run using Docker Compose:
   ```
   docker-compose up --build
   ```

## Usage

1. Access the web interface at `http://localhost:7860`
2. Enter a job description or URL to a job posting
3. Click "Get Recommendations" to receive SHL assessment suggestions
4. Or click "View All Assessments" to see the complete list of available SHL assessments

## API Endpoints

- `POST /recommend`: Recommend assessments based on job description
  - Request body: `{"text": "job description text", "url": "optional job posting URL"}`
  - Response: List of recommended assessments

- `GET /assessments`: List all available SHL assessments

- `GET /refresh-assessments`: Force refresh of assessment data

- `GET /health`: Health check endpoint

## Project Structure

- `main.py`: FastAPI application with backend logic
- `app.py`: Gradio UI
- `logger.py`: Logging configuration
- `shl_assessments_cache.json`: Cached assessment data
- `requirements.txt`: Python dependencies
- `Dockerfile`: Docker configuration
- `docker-compose.yml`: Docker Compose configuration
