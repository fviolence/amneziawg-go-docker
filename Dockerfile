# syntax=docker/dockerfile:1.7

FROM golang:1.25.8-alpine3.23 AS builder

RUN apk add --no-cache \
        bash \
        build-base \
        ca-certificates \
        git \
        linux-headers \
        libmnl-dev \
        pkgconf

WORKDIR /src

RUN git clone --depth 1 https://github.com/amnezia-vpn/amneziawg-go.git && \
    git clone --depth 1 https://github.com/amnezia-vpn/amneziawg-tools.git

RUN cd /src/amneziawg-go && \
    make -j"$(nproc)" && \
    mkdir -p /out/usr/local/bin && \
    cp amneziawg-go /out/usr/local/bin/amneziawg-go && \
    chmod +x /out/usr/local/bin/amneziawg-go

RUN cd /src/amneziawg-tools/src && \
    make -j"$(nproc)" && \
    install -Dm755 wg /out/usr/bin/awg && \
    install -Dm755 wg-quick/linux.bash /out/usr/bin/awg-quick

FROM alpine:3.23.3

RUN apk add --no-cache \
        bash \
        ca-certificates \
        iproute2 \
        iptables \
        libmnl \
        python3 \
        py3-qrcode \
        py3-pillow

COPY --from=builder /out/ /

RUN mkdir -p /etc/amnezia/amneziawg
WORKDIR /etc/amnezia

COPY entrypoint.sh /entrypoint.sh
COPY awgcfg.py /usr/local/bin/awgcfg.py

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
