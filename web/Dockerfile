FROM python:alpine

RUN pip install --upgrade flask redis requests boto3 gunicorn slack_bolt Pillow

ADD templates/ templates/
ADD web.py web.py
ADD entrypoint.sh entrypoint.sh

ENV REDIS_HOST="localhost"
ENV REDIS_PORT="6379"
ENV REDIS_DB="0"

EXPOSE 80

CMD /bin/sh entrypoint.sh
