FROM ubuntu:22.04

RUN apt-get update
RUN apt update
RUN apt clean
RUN apt-get install -y protobuf-compiler python3 python3-pip
RUN apt-get install -y memcached
RUN rm -rf /var/lib/apt/lists/*

RUN pip3 install grpcio grpcio-tools
RUN pip3 install protobuf==3.20.*
RUN pip3 install pymemcache

COPY ./ /raft-kv-store/
WORKDIR /raft-kv-store/

CMD ["sh", "/start.sh"]