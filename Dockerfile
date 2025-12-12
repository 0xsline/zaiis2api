FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (if any needed for pysqlite3 or others)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py

# Create instance directory for volume mount
RUN mkdir -p instance

EXPOSE 5000

CMD ["python", "app.py"]

