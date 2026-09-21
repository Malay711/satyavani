FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Download pre-trained model on startup
RUN python -c "from aasist_model import AASIST; AASIST.download_pretrained()"

EXPOSE 8000

CMD ["python", "server.py"]