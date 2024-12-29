FROM python:3.13

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5001

CMD ["sh", "-c", "python InputImg.py & celery -A InputImg.celery worker --loglevel=info"]