# syntax=docker/dockerfile:1
FROM rust:latest AS builder
WORKDIR /app
COPY agent/ ./agent/
WORKDIR /app/agent
RUN cargo build --release

FROM ubuntu:24.04
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/agent/target/release/agent /usr/local/bin/agent
CMD ["agent"]
