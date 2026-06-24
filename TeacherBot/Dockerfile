FROM python:3.11-slim
WORKDIR /app

# Install system deps required by some packages (if needed)
RUN apt-get update && apt-get install -y build-essential gcc libffi-dev libssl-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=5000
EXPOSE 5000
CMD ["python", "main.py"]
