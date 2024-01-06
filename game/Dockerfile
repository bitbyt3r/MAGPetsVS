FROM python:alpine

RUN pip install --upgrade redis autobahn

ADD game.py game.py
ADD entrypoint.sh entrypoint.sh

ENV AUTOBAHN_ROUTER="ws://localhost:8080/ws"
ENV REDIS_HOST="localhost"
ENV REDIS_PORT="6379"
ENV REDIS_DB="0"

EXPOSE 8080

CMD /bin/sh entrypoint.sh
