FROM python:3
RUN pip install --no-cache requests flask
WORKDIR /opt/mockth
COPY requirements.txt .
COPY mock.py .
CMD ["python", "/opt/mockth/mock.py"]
