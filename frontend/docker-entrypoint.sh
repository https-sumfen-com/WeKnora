#!/bin/sh

# 生成运行时配置文件，注入环境变量到前端
cat > /usr/share/nginx/html/config.js << EOF
window.__RUNTIME_CONFIG__ = {
  MAX_FILE_SIZE_MB: ${MAX_FILE_SIZE_MB:-50}
};
EOF

# 处理 nginx 配置
export MAX_FILE_SIZE=${MAX_FILE_SIZE_MB}M
export APP_HOST=${APP_HOST:-app}
export APP_PORT=${APP_PORT:-8080}
export APP_SCHEME=${APP_SCHEME:-http}

# iframe 嵌入策略：和 Go 后端 FrameAncestors 中间件共用同一环境变量。
# - 空 → FRAME_ANCESTORS_HEADER 替换为空字符串，nginx 不会 emit 任何 frame-ancestors 相关头（任意父域可嵌入）
# - 非空 → 生成 CSP `frame-ancestors <value>` 白名单
if [ -n "${WEKNORA_FRAME_ANCESTORS:-}" ]; then
    export FRAME_ANCESTORS_HEADER="add_header Content-Security-Policy \"frame-ancestors ${WEKNORA_FRAME_ANCESTORS}\" always;"
else
    export FRAME_ANCESTORS_HEADER=""
fi

envsubst '${MAX_FILE_SIZE} ${APP_HOST} ${APP_PORT} ${APP_SCHEME} ${FRAME_ANCESTORS_HEADER}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

# 启动 nginx
exec nginx -g 'daemon off;'
