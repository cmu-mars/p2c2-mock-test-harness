FROM python:3-alpine
RUN pip install --no-cache requests flask
WORKDIR /opt/mockth
COPY requirements.txt .
COPY mock.py .
CMD ["python", "/opt/mockth/mock.py"]
