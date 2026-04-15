#!/bin/bash
# 轮换 WEKNORA_ALIYUN_API_KEY（影响 4 个内置模型）
#
# 背景：内置模型的 API Key 在 `weknora-admin model add-builtin` 时被读取，
# 加密后存入 models.parameters；事后改 .env + 重启 app 不会生效。而且
# is_builtin=true 的模型禁止通过 HTTP API 更新（见 service/model.go:198）。
# 所以轮换只能走 CLI：unmark-builtin → delete → add-builtin。
#
# 用法：
#   1) 在阿里云控制台生成新 key
#   2) 编辑 .env：WEKNORA_ALIYUN_API_KEY=sk-new...
#   3) 运行：./scripts/rotate-aliyun-key.sh [--yes] [--no-restart]
#
# 选项：
#   --yes          跳过交互确认（CI / 自动化场景）
#   --no-restart   不自动 docker compose restart app（你想手动重启时用）

set -euo pipefail

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { printf "%b[INFO]%b %s\n"    "$BLUE"   "$NC" "$1"; }
log_warn()    { printf "%b[WARN]%b %s\n"    "$YELLOW" "$NC" "$1"; }
log_error()   { printf "%b[ERROR]%b %s\n"   "$RED"    "$NC" "$1" >&2; }
log_success() { printf "%b[OK]%b %s\n"      "$GREEN"  "$NC" "$1"; }

# 项目根目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

# 参数
AUTO_YES=0
RESTART_APP=1
for arg in "$@"; do
    case "$arg" in
        --yes|-y) AUTO_YES=1 ;;
        --no-restart) RESTART_APP=0 ;;
        -h|--help)
            sed -n '2,20p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            log_error "未知参数: $arg"
            exit 2
            ;;
    esac
done

# 1. 加载 .env，验证新 key
if [ ! -f .env ]; then
    log_error ".env 不存在；请先在项目根目录准备 .env 并设置 WEKNORA_ALIYUN_API_KEY=sk-new..."
    exit 1
fi
set -a
# shellcheck disable=SC1091
source .env
set +a

if [ -z "${WEKNORA_ALIYUN_API_KEY:-}" ]; then
    log_error ".env 里 WEKNORA_ALIYUN_API_KEY 为空；先改好再跑"
    exit 1
fi
# 简单 sk- 前缀校验，防止粘错
if [[ "$WEKNORA_ALIYUN_API_KEY" != sk-* ]]; then
    log_warn "WEKNORA_ALIYUN_API_KEY 不以 'sk-' 开头，确认没粘错？"
fi
MASK="${WEKNORA_ALIYUN_API_KEY:0:6}...${WEKNORA_ALIYUN_API_KEY: -4}"
log_info "新 key 指纹：$MASK"

# 2. 确保 weknora-admin 二进制存在
if [ ! -x ./weknora-admin ]; then
    log_info "weknora-admin 不存在，正在执行 make build-admin ..."
    make build-admin
fi

# 3. 待轮换的 4 个内置模型（与 docs/上线流程.md 第 2 步一致）
# 每行格式：ID|TYPE|NAME|EXTRA_FLAGS
MODELS=(
    "builtin-llm-default|KnowledgeQA|qwen3.6-plus|"
    "builtin-embedding-default|Embedding|text-embedding-v4|--dimension 1024"
    "builtin-rerank-default|Rerank|qwen3-vl-rerank|"
    "builtin-vlm-default|VLLM|qwen-vl-max|--supports-vision"
)

echo
log_info "即将轮换下列 4 个内置模型的 API Key："
for entry in "${MODELS[@]}"; do
    IFS='|' read -r id mtype mname extra <<< "$entry"
    printf "  - %-30s type=%-12s name=%-22s\n" "$id" "$mtype" "$mname"
done
echo

if [ "$AUTO_YES" -ne 1 ]; then
    read -rp "确认继续？[y/N] " ans
    case "$ans" in
        y|Y|yes|YES) ;;
        *) log_info "已取消"; exit 0 ;;
    esac
fi

# 4. 显示轮换前状态（便于出问题时人工比对）
echo
log_info "轮换前 model list："
./weknora-admin model list || true

# 5. 逐个 unmark → delete → add-builtin
for entry in "${MODELS[@]}"; do
    IFS='|' read -r id mtype mname extra <<< "$entry"
    echo
    log_info "[$id] 开始"

    # 5a. unmark-builtin（可能已不是 builtin，忽略错误）
    if ./weknora-admin model unmark-builtin --id "$id" 2>/dev/null; then
        log_success "[$id] unmark-builtin 完成"
    else
        log_warn "[$id] unmark-builtin 失败或模型不存在（继续尝试 delete）"
    fi

    # 5b. delete（可能已不存在，忽略错误）
    if ./weknora-admin model delete --id "$id" 2>/dev/null; then
        log_success "[$id] delete 完成"
    else
        log_warn "[$id] delete 失败或模型不存在（继续尝试 add-builtin）"
    fi

    # 5c. add-builtin（会从 $WEKNORA_ALIYUN_API_KEY 读新 key）
    # shellcheck disable=SC2086
    ./weknora-admin model add-builtin \
        --id "$id" --type "$mtype" --provider aliyun --name "$mname" $extra
    log_success "[$id] add-builtin 完成（已注入新 key 并加密落库）"
done

# 6. 显示轮换后状态
echo
log_info "轮换后 model list："
./weknora-admin model list

# 7. 重启 app 清模型缓存
echo
if [ "$RESTART_APP" -eq 1 ]; then
    if command -v docker >/dev/null 2>&1 && docker compose ps app >/dev/null 2>&1; then
        log_info "docker compose restart app ..."
        docker compose restart app
        log_success "app 已重启"
    else
        log_warn "检测不到运行中的 app 服务，跳过自动重启；请手动 docker compose restart app"
    fi
else
    log_warn "--no-restart 已指定；请手动执行 docker compose restart app 让新 key 生效"
fi

echo
log_success "✓ 轮换完成"
log_info   "建议：前端发一条对话验证 LLM 回复正常；验证无误后回阿里云控制台删掉旧 key"
