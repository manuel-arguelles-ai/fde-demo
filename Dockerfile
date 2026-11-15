FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py eval_set.json ./
COPY docs/ ./docs/
COPY static/ ./static/
ENV FDE_MODEL=openai/gpt-oss-120b
EXPOSE 8899
CMD ["uvicorn", "app:api", "--host", "0.0.0.0", "--port", "8899"]
