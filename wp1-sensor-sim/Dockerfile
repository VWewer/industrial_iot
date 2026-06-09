FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY data/ ./data/

ENV MQTT_BROKER_HOST=mosquitto \
    MQTT_BROKER_PORT=1883 \
    SENSOR_PUBLISH_INTERVAL_S=5 \
    PLANT_ID=regensburg \
    OVEN_ID=oven-01 \
    CYCLE_TIME_COMPRESSION=60.0 \
    CONTROL_API_PORT=8000 \
    LOG_LEVEL=INFO

EXPOSE 8000

CMD ["python", "-m", "src.main"]
