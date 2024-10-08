# Use the official Python image as a base
FROM python:3.12.5-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y curl build-essential && \
    apt-get remove -y curl && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy only the poetry files to install dependencies first
COPY pyproject.toml /app/
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install -r requirements.txt --no-cache-dir
RUN mkdir -p app/instance
# Copy the rest of the application code
COPY src/app.py /app
COPY src/config.py /app
COPY src/static /app/static
COPY src/templates /app/templates


# Expose port 80 for the Flask-SocketIO server
EXPOSE 10000

# Set the entry point to run the application
CMD ["python", "app.py"]
