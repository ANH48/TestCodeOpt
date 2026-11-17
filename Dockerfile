FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY optibot ./optibot
COPY main.py ask.py ./

RUN useradd --create-home optibot && chown -R optibot /app
USER optibot

ENTRYPOINT ["python"]
CMD ["main.py"]
