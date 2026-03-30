# syntax=docker/dockerfile:1
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY ingestion/ ./
RUN go mod tidy && go build -o ingestion_server .

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/ingestion_server .
EXPOSE 8080
CMD ["./ingestion_server"]
