FROM python:3.12-slim
WORKDIR /app
COPY deploy/requirements.txt ./requirements.txt
RUN pip install -r ./requirements.txt
COPY .. .
CMD ["python", "-m", "service.start"]
