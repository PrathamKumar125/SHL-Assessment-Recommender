import gradio as gr
import requests
import os
from dotenv import load_dotenv
from logger import ui_logger

# Load environment variables
load_dotenv()
ui_logger.info("Environment variables loaded")

# API URL (default to localhost when running locally)
API_URL = os.getenv("API_URL", "http://localhost:8000")
ui_logger.info(f"Using API URL: {API_URL}")

def recommend_assessments(text_input, url_input):
    """Function to call the FastAPI endpoint and display results"""
    if not text_input and not url_input:
        ui_logger.warning("Request with no text or URL provided")
        return "Please provide either a job description text or a URL."
    
    # Prepare request data
    data = {}
    if text_input:
        ui_logger.info(f"Processing text input (length: {len(text_input)})")
        data["text"] = text_input
    if url_input:
        ui_logger.info(f"Processing URL input: {url_input}")
        data["url"] = url_input
    
    try:
        # Call FastAPI endpoint
        ui_logger.debug(f"Sending request to {API_URL}/recommend")
        response = requests.post(f"{API_URL}/recommend", json=data)
        response.raise_for_status()
        
        # Process results
        results = response.json()
        recommendations = results.get("recommendations", [])
        
        if not recommendations:
            ui_logger.warning("No recommendations received")
            return "No relevant assessments found. Please try a more detailed job description."
        
        ui_logger.info(f"Received {len(recommendations)} recommendations")
        
        # Format output as HTML table
        html_output = """
        <style>
        table {
            border-collapse: collapse;
            width: 100%;
            margin-top: 20px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        a {
            color: #0366d6;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        </style>
        <table>
            <tr>
                <th>Assessment Name</th>
                <th>Remote Testing</th>
                <th>Adaptive/IRT Support</th>
                <th>Duration</th>
                <th>Test Type</th>
            </tr>
        """
        
        for assessment in recommendations:
            name = assessment.get("name", "")
            url = assessment.get("url", "")
            remote = "Yes" if assessment.get("remote_testing", False) else "No"
            adaptive = "Yes" if assessment.get("adaptive_support", False) else "No"
            duration = assessment.get("duration", "")
            test_type = assessment.get("test_type", "")
            
            html_output += f"""
            <tr>
                <td><a href="{url}" target="_blank">{name}</a></td>
                <td>{remote}</td>
                <td>{adaptive}</td>
                <td>{duration}</td>
                <td>{test_type}</td>
            </tr>
            """
        
        html_output += "</table>"
        
        # Add explanation below the table
        html_output += """
        <div style="margin-top: 20px; font-size: 14px; color: #666;">
            <p>These assessments are recommended based on the job description provided. 
            Click on the assessment name to learn more about each assessment on the SHL website.</p>
        </div>
        """
        
        return html_output
    
    except Exception as e:
        ui_logger.error(f"Error in recommend_assessments: {str(e)}")
        return f"Error: {str(e)}"

# Create Gradio interface
with gr.Blocks(title="SHL Assessment Recommender", theme=gr.themes.Base()) as demo:
    gr.Markdown("# SHL Assessment Recommender")
    gr.Markdown("Enter a job description or provide a URL to get relevant SHL assessment recommendations.")
    
    with gr.Row():
        with gr.Column():
            text_input = gr.Textbox(
                label="Job Description", 
                placeholder="Enter job description or requirements here...",
                lines=10
            )
            url_input = gr.Textbox(
                label="URL (Optional)",
                placeholder="Or enter a URL to a job posting..."
            )
            with gr.Row():
                submit_btn = gr.Button("Get Recommendations", variant="primary")
                view_all_btn = gr.Button("View All Assessments", variant="secondary")
    
    output = gr.HTML(label="Recommendations")
    
    submit_btn.click(
        fn=recommend_assessments,
        inputs=[text_input, url_input],
        outputs=output
    )
    
    def view_all_assessments():
        try:
            ui_logger.info("Requesting all assessments")
            response = requests.get(f"{API_URL}/assessments")
            response.raise_for_status()
            result = response.json()
            assessments = result.get("assessments", [])
            
            ui_logger.info(f"Received {len(assessments)} assessments")
            
            # Format all assessments as HTML table
            html_output = """
            <style>
            table {
                border-collapse: collapse;
                width: 100%;
                margin-top: 20px;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
                font-weight: bold;
            }
            tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            a {
                color: #0366d6;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
            </style>
            <h3>All Available SHL Assessments</h3>
            <table>
                <tr>
                    <th>Assessment Name</th>
                    <th>Remote Testing</th>
                    <th>Adaptive/IRT Support</th>
                    <th>Duration</th>
                    <th>Test Type</th>
                </tr>
            """
            
            for assessment in assessments:
                name = assessment.get("name", "")
                url = assessment.get("url", "")
                remote = "Yes" if assessment.get("remote_testing", False) else "No"
                adaptive = "Yes" if assessment.get("adaptive_support", False) else "No"
                duration = assessment.get("duration", "")
                test_type = assessment.get("test_type", "")
                
                html_output += f"""
                <tr>
                    <td><a href="{url}" target="_blank">{name}</a></td>
                    <td>{remote}</td>
                    <td>{adaptive}</td>
                    <td>{duration}</td>
                    <td>{test_type}</td>
                </tr>
                """
            
            html_output += "</table>"
            return html_output
            
        except Exception as e:
            ui_logger.error(f"Error in view_all_assessments: {str(e)}")
            return f"Error: {str(e)}"
    
    view_all_btn.click(
        fn=view_all_assessments,
        inputs=[],
        outputs=output
    )

if __name__ == "__main__":
    ui_logger.info("Starting Gradio UI")
    # demo.launch()
    demo.launch(server_name="0.0.0.0", server_port=7860)
    ui_logger.info("Gradio UI stopped")
