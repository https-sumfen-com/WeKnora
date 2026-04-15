#!/bin/bash

REGISTRY="registry.cn-shenzhen.aliyuncs.com/sf-work"

TAG=${1:-latest}

docker login --username=ian.liu@foxmail.com registry.cn-shenzhen.aliyuncs.com

docker tag wechatopenai/weknora-ui:latest $REGISTRY/weknora-ui:$TAG
docker tag wechatopenai/weknora-docreader:latest $REGISTRY/weknora-docreader:$TAG
docker tag wechatopenai/weknora-app:latest $REGISTRY/weknora-app:$TAG


docker push $REGISTRY/weknora-ui:$TAG
docker push $REGISTRY/weknora-docreader:$TAG
docker push $REGISTRY/weknora-app:$TAG

echo "push done. tag: $TAG"