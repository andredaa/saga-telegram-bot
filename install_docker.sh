#!/bin/bash

docker stop sagabot_i
docker rm sagabot_i
docker build -t=sagabot ./
docker run -d --name sagabot_i sagabot
docker logs -f sagabot_i