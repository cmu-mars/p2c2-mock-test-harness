FROM python:3-alpine
COPY requirements.txt .
RUN pip install --no-cache -r requirements.txt
WORKDIR /opt/mockth
COPY mock.py .
ENTRYPOINT ["python", "-u", "/opt/mockth/mock.py"]
CMD ["-p", "5001", "--url-ta", "http://cp2_ta:5000", "--debug"]
