#!/bin/bash

REGISTRY="registry.cn-shenzhen.aliyuncs.com/sf-work"

TAG=${1:-latest}
COMPONENT=$2

docker login --username=ian.liu@foxmail.com registry.cn-shenzhen.aliyuncs.com

if [ -z "$COMPONENT" ]; then
    # 没有指定组件，推送全部
    docker tag wechatopenai/weknora-ui:latest $REGISTRY/weknora-ui:$TAG
    docker tag wechatopenai/weknora-docreader:latest $REGISTRY/weknora-docreader:$TAG
    docker tag wechatopenai/weknora-app:latest $REGISTRY/weknora-app:$TAG

    docker push $REGISTRY/weknora-ui:$TAG
    docker push $REGISTRY/weknora-docreader:$TAG
    docker push $REGISTRY/weknora-app:$TAG

    echo "push all done. tag: $TAG"
else
    # 推送指定组件
    case $COMPONENT in
        ui)
            docker tag wechatopenai/weknora-ui:latest $REGISTRY/weknora-ui:$TAG
            docker push $REGISTRY/weknora-ui:$TAG
            ;;
        docreader)
            docker tag wechatopenai/weknora-docreader:latest $REGISTRY/weknora-docreader:$TAG
            docker push $REGISTRY/weknora-docreader:$TAG
            ;;
        app)
            docker tag wechatopenai/weknora-app:latest $REGISTRY/weknora-app:$TAG
            docker push $REGISTRY/weknora-app:$TAG
            ;;
        *)
            echo "用法: $0 [tag] [ui|docreader|app]"
            echo "示例:"
            echo "  $0 latest ui        # 只推送 ui"
            echo "  $0 v1.0 app        # 只推送 app"
            echo "  $0 latest          # 推送全部"
            exit 1
            ;;
    esac
    echo "push $COMPONENT done. tag: $TAG"
fi