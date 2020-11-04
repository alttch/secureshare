from altertech/pytpl:37
COPY ./secureshare-supervisord.conf /etc/supervisor/conf.d/
RUN /opt/venv/bin/pip3 install --no-cache-dir secureshare==0.0.12
