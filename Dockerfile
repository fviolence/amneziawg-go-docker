# Use Ubuntu as the base image
FROM ubuntu:22.04
ARG TARGETARCH

# Verify TARGETARCH
RUN echo "Building for TARGETARCH=${TARGETARCH}"

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && \
    apt-get install -y \
        build-essential \
        wireguard-tools \
        iproute2 \
        iptables \
        curl \
        wget \
        python3 \
        python3-pip \
        python3-qrcode \
        git \
        software-properties-common && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Golang
RUN wget https://go.dev/dl/go1.23.5.linux-${TARGETARCH}.tar.gz && \
    tar -C /usr/local -xzf go1.23.5.linux-${TARGETARCH}.tar.gz && \
    rm go1.23.5.linux-${TARGETARCH}.tar.gz

# Set Golang environment variables
ENV PATH="/usr/local/go/bin:$PATH"
ENV GOPATH=/root/go

# Build amneziawg-go
RUN git clone https://github.com/amnezia-vpn/amneziawg-go.git && \
    cd amneziawg-go && \
    make -j `nproc` && \
    chmod +x amneziawg-go && \
    mv amneziawg-go /usr/local/bin/amneziawg-go && \
    cd .. && rm -rf amneziawg-go

RUN git clone https://github.com/amnezia-vpn/amneziawg-tools && \
    cd amneziawg-tools/src && \
    make -j`nproc` && make install &&\
    cd ../.. && rm -rf amneziawg-tools

# Create directory for configs and scripts
RUN mkdir -p /etc/amnezia/amneziawg
WORKDIR /etc/amnezia

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy awgcfg.py script
COPY awgcfg.py /etc/amnezia/awgcfg.py

# Run entrypoint
ENTRYPOINT ["/entrypoint.sh"]