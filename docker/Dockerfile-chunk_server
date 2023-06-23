FROM python:3.11.4-alpine3.18

COPY . /app/

WORKDIR /app

RUN pip install -r requirements.txt

CMD ["python", "app.py"]