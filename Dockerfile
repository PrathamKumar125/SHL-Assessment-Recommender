FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose ports for FastAPI (8000) and Gradio (7860)
EXPOSE 8000 7860

# Create logs directory
RUN mkdir -p logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV API_URL=http://localhost:8000

# Create a startup script to run both services
RUN echo '#!/bin/bash \n\
python main.py & \n\
sleep 5 \n\
python app.py \n\
' > /app/start.sh && chmod +x /app/start.sh

# Command to run both FastAPI and Gradio applications
CMD ["/app/start.sh"]
