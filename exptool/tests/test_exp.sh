#!/usr/bin/env bash
# exp 的冒烟测试。只用 local 模式：不需要集群，不需要 tmux，不需要 ssh。
#
# 跑法：
#   bash tests/test_exp.sh
#
# 解释器会自动探测（python3 / python / py），也可以用 REMOTE_PYTHON 环境变量指定。

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TOOL="$(dirname "$HERE")"
FAILED=0

pass() { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; FAILED=$((FAILED + 1)); }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 探测一个真的能跑的解释器。Windows 上 python3 往往是 Microsoft Store 的占位程序，
# 执行时直接退出（不报错也不输出），会让所有涉及进度读取器的断言假失败。
if [ -n "${REMOTE_PYTHON:-}" ]; then
  PY="$REMOTE_PYTHON"
else
  PY=""
  for cand in python3 python py; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'pass' >/dev/null 2>&1; then
      PY="$cand"; break
    fi
  done
  if [ -z "$PY" ]; then
    echo "找不到可用的 python 解释器（试过 python3 / python / py），用 REMOTE_PYTHON 指定一个。" >&2
    exit 1
  fi
fi

# 断言里有中文，必须让解释器按 UTF-8 输出；Windows 上默认按 GBK 写，中文匹配不上。
export PYTHONIOENCODING=utf-8

# 登记表用示例那份，机器列是 local，不走 ssh
cat > "$TMP/config" <<EOF
RUNS_CONF="$TOOL/runs.conf.example"
REMOTE_PYTHON="$PY"
EOF

# 找不到登记表的情况
cat > "$TMP/bad.conf" <<EOF
RUNS_CONF="$TMP/does-not-exist.conf"
REMOTE_PYTHON="$PY"
EOF

run() { EXPT_CONF="$TMP/config" bash "$TOOL/exp" "$@" 2>&1; }

echo "exp help"
out="$(run help)"; code=$?
[ $code -eq 0 ] && pass "退出码 0" || fail "退出码 $code"
case "$out" in *"exp status"*) pass "列出了 status" ;; *) fail "没列出 status" ;; esac

echo "exp list"
out="$(run list)"; code=$?
[ $code -eq 0 ] && pass "退出码 0" || fail "退出码 $code"
case "$out" in *demo-sft*) pass "能看到 demo-sft" ;; *) fail "看不到 demo-sft" ;; esac

echo "exp status demo-sft"
out="$(run status demo-sft)"; code=$?
[ $code -eq 0 ] && pass "退出码 0" || fail "退出码 $code"
case "$out" in *metrics.jsonl*) pass "找到了指标来源" ;; *) fail "没找到指标来源" ;; esac
case "$out" in *loss*) pass "显示了 loss" ;; *) fail "没有 loss" ;; esac
case "$out" in *"step "*) fail "混进了 step 元数据" ;; *) pass "没混进 step 元数据" ;; esac
case "$out" in *"切 8 段"*) pass "默认切 8 段" ;; *) fail "没切 8 段" ;; esac

echo "exp status（不带参数，默认取第一行）"
out="$(run status)"; code=$?
[ $code -eq 0 ] && pass "退出码 0" || fail "退出码 $code"

echo "exp config demo-sft"
out="$(run config demo-sft)"; code=$?
[ $code -eq 0 ] && pass "退出码 0" || fail "退出码 $code"
case "$out" in *echo*) pass "打印出了 launch.sh" ;; *) fail "没打印 launch.sh" ;; esac

echo "exp errors demo-sft"
out="$(run errors demo-sft)"; code=$?
[ $code -eq 0 ] && pass "退出码 0" || fail "退出码 $code"

echo "事前记录（exp plan / status）"
out="$(run status demo-sft)"
case "$out" in *"判据: 用固定 dev 集"*) pass "status 把判据印在指标旁" ;; *) fail "status 没带出判据" ;; esac

out="$(run plan demo-sft)"; code=$?
[ $code -eq 0 ] && pass "exp plan 退出码 0" || fail "exp plan 退出码 $code"
case "$out" in *"预算与止损"*) pass "打印了 PLAN.md 全文" ;; *) fail "没打印全文" ;; esac

# 没写 / 半角冒号 两种实验，共用一份临时登记表
mkdir -p "$TMP/noplan" "$TMP/halfwidth"
printf '判据: 半角冒号也得能读出来\n' > "$TMP/halfwidth/PLAN.md"
cat > "$TMP/plan-runs.conf" <<EOF
名字   机器   目录             方法  tmux  说明
fresh  local  $TMP/noplan      sft   -     没写事前记录
half   local  $TMP/halfwidth   sft   -     半角冒号
EOF
cat > "$TMP/plan.conf" <<EOF
RUNS_CONF="$TMP/plan-runs.conf"
REMOTE_PYTHON="$PY"
EOF
planrun() { EXPT_CONF="$TMP/plan.conf" bash "$TOOL/exp" "$@" 2>&1; }

out="$(planrun status fresh)"
case "$out" in *"没有 PLAN.md"*) pass "没写时 status 会提醒" ;; *) fail "没写时 status 没提醒" ;; esac

out="$(planrun plan fresh)"; code=$?
[ $code -eq 0 ] && pass "exp plan 生成模板" || fail "生成模板失败（退出码 $code）"
[ -f "$TMP/noplan/PLAN.md" ] && pass "PLAN.md 真的落盘了" || fail "PLAN.md 没落盘"
case "$(cat "$TMP/noplan/PLAN.md" 2>/dev/null)" in *"判据："*) pass "模板里有判据一项" ;; *) fail "模板缺判据" ;; esac

out="$(planrun status half)"
case "$out" in *"判据: 半角冒号也得能读出来"*) pass "半角冒号也能读出来" ;; *) fail "半角冒号没读出来" ;; esac

echo "错误路径"
out="$(run nonsense)"; code=$?
[ $code -ne 0 ] && pass "不认识的命令会报错" || fail "不认识的命令居然成功了"

out="$(run status no-such-run)"; code=$?
[ $code -ne 0 ] && pass "不认识的实验会报错" || fail "不认识的实验居然成功了"

out="$(EXPT_CONF="$TMP/bad.conf" bash "$TOOL/exp" list 2>&1)"; code=$?
[ $code -ne 0 ] && pass "登记表不存在时报错" || fail "登记表不存在时居然成功了"
case "$out" in *runs.conf*) pass "报错里指明了 runs.conf" ;; *) fail "报错没提 runs.conf" ;; esac

echo
if [ "$FAILED" -gt 0 ]; then
  echo "$FAILED 项没过。"
  exit 1
fi
echo "全部通过。"
