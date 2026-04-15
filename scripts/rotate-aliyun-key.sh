#!/bin/bash
# 初始化 / 轮换 WEKNORA_ALIYUN_API_KEY（影响 4 个内置模型）
#
# 单脚本覆盖两种场景，按当前 DB 中已存在的内置模型数量自动切换：
#   - 初始化（0/4 存在）：只跑 add-builtin
#   - 轮换   （4/4 存在）：unmark-builtin → delete → add-builtin
#   - 混合   （部分存在）：存在的走轮换路径，缺失的走初始化路径
#
# 背景：内置模型的 API Key 在 `weknora-admin model add-builtin` 时被读取，
# 加密后存入 models.parameters；事后改 .env + 重启 app 不会生效。而且
# is_builtin=true 的模型禁止通过 HTTP API 更新（见 service/model.go:198）。
# 所以轮换只能走 CLI：unmark-builtin → delete → add-builtin。
#
# 用法：
#   1) 阿里云控制台：新装时生成 key，轮换时生成新 key
#   2) 编辑 .env：WEKNORA_ALIYUN_API_KEY=sk-xxx
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
            sed -n '2,24p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            log_error "未知参数: $arg"
            exit 2
            ;;
    esac
done

# 1. 加载 .env，验证 key
if [ ! -f .env ]; then
    log_error ".env 不存在；请先在项目根目录准备 .env 并设置 WEKNORA_ALIYUN_API_KEY=sk-..."
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
log_info "key 指纹：$MASK"

# 2. 确保 weknora-admin 二进制存在
if [ ! -x ./weknora-admin ]; then
    log_info "weknora-admin 不存在，正在执行 make build-admin ..."
    make build-admin
fi

# 3. 目标 4 个内置模型（与 docs/上线流程.md 第 2 步一致）
# 每行格式：ID|TYPE|NAME|EXTRA_FLAGS
MODELS=(
    "builtin-llm-default|KnowledgeQA|qwen3.6-plus|"
    "builtin-embedding-default|Embedding|text-embedding-v4|--dimension 1024"
    "builtin-rerank-default|Rerank|qwen3-vl-rerank|"
    "builtin-vlm-default|VLLM|qwen-vl-max|--supports-vision"
)
TOTAL=${#MODELS[@]}

# 4. 查询现有内置模型，决定走哪个模式
log_info "查询当前 DB 中的内置模型..."
EXISTING_IDS=$(./weknora-admin model list 2>/dev/null | awk 'NR>1 {print $1}' || true)

# 每个目标 ID 是否已存在
declare -a EXISTS_FLAGS=()
EXISTING_COUNT=0
for entry in "${MODELS[@]}"; do
    IFS='|' read -r id _ _ _ <<< "$entry"
    if echo "$EXISTING_IDS" | grep -qx "$id"; then
        EXISTS_FLAGS+=(1)
        EXISTING_COUNT=$((EXISTING_COUNT + 1))
    else
        EXISTS_FLAGS+=(0)
    fi
done

if [ "$EXISTING_COUNT" -eq 0 ]; then
    MODE="init"
    MODE_LABEL="初始化"
elif [ "$EXISTING_COUNT" -eq "$TOTAL" ]; then
    MODE="rotate"
    MODE_LABEL="轮换"
else
    MODE="mixed"
    MODE_LABEL="混合（$EXISTING_COUNT/$TOTAL 已存在，其余补建）"
fi

echo
log_info "运行模式：【$MODE_LABEL】"
log_info "目标模型："
i=0
for entry in "${MODELS[@]}"; do
    IFS='|' read -r id mtype mname _ <<< "$entry"
    if [ "${EXISTS_FLAGS[$i]}" -eq 1 ]; then
        printf "  [轮换] %-30s type=%-12s name=%-22s\n" "$id" "$mtype" "$mname"
    else
        printf "  [新建] %-30s type=%-12s name=%-22s\n" "$id" "$mtype" "$mname"
    fi
    i=$((i + 1))
done
echo

if [ "$AUTO_YES" -ne 1 ]; then
    read -rp "确认继续？[y/N] " ans
    case "$ans" in
        y|Y|yes|YES) ;;
        *) log_info "已取消"; exit 0 ;;
    esac
fi

# 5. 仅在有模型需要轮换时打印前置 list（初始化模式下 DB 通常是空的，没必要啰嗦）
if [ "$MODE" != "init" ]; then
    echo
    log_info "操作前 model list："
    ./weknora-admin model list || true
fi

# 6. 逐个处理：存在 → unmark → delete → add-builtin；不存在 → 直接 add-builtin
i=0
for entry in "${MODELS[@]}"; do
    IFS='|' read -r id mtype mname extra <<< "$entry"
    echo
    if [ "${EXISTS_FLAGS[$i]}" -eq 1 ]; then
        log_info "[$id] 已存在，执行轮换（unmark → delete → add-builtin）"

        # unmark-builtin（对象可能已是非 builtin；失败也不致命）
        if ./weknora-admin model unmark-builtin --id "$id" 2>/dev/null; then
            log_success "[$id] unmark-builtin 完成"
        else
            log_warn "[$id] unmark-builtin 失败（可能已是非 builtin，继续尝试 delete）"
        fi

        # delete（幂等兜底）
        if ./weknora-admin model delete --id "$id" 2>/dev/null; then
            log_success "[$id] delete 完成"
        else
            log_warn "[$id] delete 失败（继续尝试 add-builtin）"
        fi
    else
        log_info "[$id] 不存在，执行初始化（直接 add-builtin）"
    fi

    # add-builtin（从 $WEKNORA_ALIYUN_API_KEY 读 key）
    # shellcheck disable=SC2086
    ./weknora-admin model add-builtin \
        --id "$id" --type "$mtype" --provider aliyun --name "$mname" $extra
    log_success "[$id] add-builtin 完成（已注入当前 key 并加密落库）"

    i=$((i + 1))
done

# 7. 后置 list
echo
log_info "操作后 model list："
./weknora-admin model list

# 8. 重启 app 清模型缓存（仅轮换/混合模式需要；初始化模式 app 若还没起，不需要 restart）
echo
if [ "$MODE" = "init" ]; then
    log_info "初始化模式：若 app 容器尚未首次启动，直接 docker compose up -d 即可；若已在运行，建议 docker compose restart app"
elif [ "$RESTART_APP" -eq 1 ]; then
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
if [ "$MODE" = "init" ]; then
    log_success "✓ 初始化完成"
    log_info   "下一步：确认 app/frontend 容器已运行，然后走 docs/上线流程.md 的后续验证步骤"
else
    log_success "✓ 轮换完成"
    log_info   "建议：前端发一条对话验证 LLM 回复正常；验证无误后回阿里云控制台删掉旧 key"
fi
