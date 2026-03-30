# syntax=docker/dockerfile:1
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY alerts/ ./
RUN go mod init projectsys/alerts && go get github.com/redis/go-redis/v9 && go build -o alerts_server .

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/alerts_server .
CMD ["./alerts_server"]
