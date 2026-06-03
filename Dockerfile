# Stage 1 — compile psutil (gcc required on Alpine)
FROM python:3.12-alpine AS builder
RUN apk add --no-cache gcc musl-dev linux-headers
RUN pip install --no-cache-dir --target=/deps psutil

# Stage 2 — lean final image (~60 MB)
FROM python:3.12-alpine
COPY --from=builder /deps /deps
COPY monitor-dashboard.py /app/monitor-dashboard.py
WORKDIR /app
ENV PYTHONPATH=/deps
EXPOSE 80
CMD ["python", "-u", "monitor-dashboard.py"]
