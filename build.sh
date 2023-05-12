# This file is to be used for local building, ie, without docker.
sudo rm -rf ./logs/logcache/server*

# build grpc files
echo '|                             (0 of 5) Building kvstore.proto\r\c'
python3 -m grpc_tools.protoc --proto_path=protos --python_out=./ --grpc_python_out=./ protos/kvstore.proto
echo '||                            (1 of 5) Building raft.proto\r\c'
python3 -m grpc_tools.protoc --proto_path=protos --python_out=./ --grpc_python_out=./ protos/raft.proto

# kill and remove containers
echo '|||                           (2 of 5) Cleaning old containers\r\c'
cd docker; docker compose down; docker compose kill; docker compose rm -f; cd ..; docker kill $(docker ps -qa); docker rm $(docker ps -qa)

# build image named `kvstore`
echo '||||                          (3 of 5) Building kvstore image\r\c'
docker build -t kvstore -f ./docker/Dockerfile .

# orchestrate containers
echo '|||||                         (4 of 5) Running docker compose\r\c'
docker compose -f ./docker/docker-compose.yaml up -d

echo '||||||                        (5 of 5) Finished\r\c'
echo '\n'
