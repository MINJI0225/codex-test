FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn pydantic pyyaml jsonschema httpx

# build context가 ./gateway 이므로 현재 폴더를 그대로 복사
COPY . /app

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
