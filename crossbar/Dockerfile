FROM crossbario/crossbar

USER root
ADD config.json /mynode/.crossbar/config.json
RUN chown -R crossbar:crossbar /mynode
USER crossbar
ENTRYPOINT ["crossbar", "start", "--cbdir", "/mynode/.crossbar"]