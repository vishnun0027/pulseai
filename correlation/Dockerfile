# syntax=docker/dockerfile:1
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY correlation/ ./
RUN go mod init projectsys/correlation && go get github.com/redis/go-redis/v9 && go build -o correlation_server .

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/correlation_server .
CMD ["./correlation_server"]
