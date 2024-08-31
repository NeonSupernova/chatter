# Use the official Python image as a base
FROM python:3.12.5-slim

# Set environment variables for Poetry
ENV POETRY_VERSION=1.5.1
ENV POETRY_HOME=/opt/poetry
ENV PATH="$POETRY_HOME/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y curl build-essential && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    apt-get remove -y curl && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy only the poetry files to install dependencies first
COPY pyproject.toml /app/

# Install Python dependencies
RUN poetry install --no-root --no-interaction --no-ansi

# Copy the rest of the application code
COPY . /app

# Expose port 80 for the Flask-SocketIO server
EXPOSE 80

# Set the entry point to run the application
CMD ["poetry", "run", "python", "main.py"]