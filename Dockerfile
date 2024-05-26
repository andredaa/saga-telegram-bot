FROM python:3.11

RUN mkdir /app
WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

ENTRYPOINT ["python3", "-u", "main.py"]
CMD []