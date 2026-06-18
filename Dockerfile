FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Спершу залежності — щоб кешувати шар при незмінному requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Потім код застосунку
COPY . .

# Каталог для бази даних (монтується як том)
RUN mkdir -p /app/data
VOLUME ["/app/data"]

CMD ["python", "run.py"]
