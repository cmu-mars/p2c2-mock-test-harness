FROM python:3-alpine
RUN pip install --no-cache requests flask
WORKDIR /opt/mockth
COPY requirements.txt .
COPY mock.py .
ENTRYPOINT ["python", "/opt/mockth/mock.py"]
CMD ["-p", "5001", "--url-ta", "http://cp2_ta:5000", "--debug"]
