FROM nginx:1.27-alpine

# Replace the default config with ours.
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/portal.conf

# Healthcheck hits the Django /healthz through the proxy.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget --spider -q http://127.0.0.1:80/healthz || exit 1
