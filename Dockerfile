FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
EXPOSE 8765
CMD ["pdf2md-web", "--host", "0.0.0.0", "--port", "8765", "--no-browser"]
ENV PYTHONUNBUFFERED=1
