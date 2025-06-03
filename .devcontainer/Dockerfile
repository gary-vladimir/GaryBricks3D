FROM python:3.11-slim

# Set the working directory
WORKDIR /workspace

# Copy requirements.txt
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt
