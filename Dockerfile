# Stage 1 — compile psutil (gcc required on Alpine)
FROM python:3.12-alpine AS builder
RUN apk add --no-cache gcc musl-dev linux-headers
RUN pip install --no-cache-dir --target=/deps psutil

# Stage 2 — lean final image (~65 MB)
FROM python:3.12-alpine
# util-linux provides the `last` command for login history
RUN apk add --no-cache util-linux
COPY --from=builder /deps /deps
# Use the Docker-specific dashboard (reads /proc/1/net/dev, port-based service
# detection, fixed process listing) instead of the bare-metal install version.
COPY monitor-dashboard-docker.py /app/monitor-dashboard.py
WORKDIR /app
ENV PYTHONPATH=/deps
EXPOSE 80
CMD ["python", "-u", "monitor-dashboard.py"]
