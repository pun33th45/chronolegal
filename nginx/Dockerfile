FROM nginx:1.27-alpine

RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/nginx.conf
COPY default.conf /etc/nginx/conf.d/default.conf

# Placeholder SSL certs for local dev (replaced in prod by volume mount)
RUN mkdir -p /etc/nginx/ssl && \
    apk add --no-cache openssl && \
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout /etc/nginx/ssl/privkey.pem \
        -out /etc/nginx/ssl/fullchain.pem \
        -subj "/C=IN/ST=Delhi/L=Delhi/O=ChronoLegal/CN=localhost" && \
    apk del openssl

EXPOSE 80 443

# 127.0.0.1, not localhost: confirmed via CI's docker-compose-prod-smoke
# job that this healthcheck reliably fails with "Connection refused" —
# `default.conf` isn't nginx's stock config (its own entrypoint log
# confirms it skips auto-adding an IPv6 listener for non-default configs,
# see 10-listen-on-ipv6-by-default.sh), so nginx only binds IPv4, but
# `wget http://localhost/...` resolves "localhost" to ::1 first on this
# base image and gets refused before ever falling back to IPv4.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q -O- http://127.0.0.1/health || exit 1
