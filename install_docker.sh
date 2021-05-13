#!/bin/bash

docker stop sagabot_i
docker rm sagabot_i
docker build -t=sagabot ./ --no-cache
docker run -d --name sagabot_i sagabot --restart=always
docker logs -f sagabot_i