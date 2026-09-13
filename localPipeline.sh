#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

# One command from a fresh clone to a verified, runnable tokenusage2. It finds
# Python 3.14, creates .venv, installs the pinned development tools, runs every
# quality gate, builds sdist and wheel, proves the wheel works from a clean
# environment, checks .venv/bin/tokenusage2 and launches the dashboard. Every
# stage is timed, and the run closes with a summary and a verdict. CI and the
# release workflow run the same script with --noRun.

# Stage functions are called indirectly through run_stage (SC2317 before
# ShellCheck 0.10, SC2329 since).
# shellcheck disable=SC2317,SC2329

set -uo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly ROOT_DIR
readonly VENV_DIR="${ROOT_DIR}/.venv"
readonly VENV_PYTHON="${VENV_DIR}/bin/python"
readonly APP="${VENV_DIR}/bin/tokenusage2"
readonly COVERAGE_GATE=95

RUN_APP=true
FIX=false
VERBOSE=false
REPORT_DIR=""
LOG_DIR=""
REMOVE_LOG_DIR=true
BASE_PYTHON=""
DETAILS=""
PIPELINE_START=""
declare -a SUMMARY=()
declare -a FAILED=()
MANDATORY=0
PASSED=0

usage() {
    cat <<'EOF'
Usage: ./localPipeline.sh [--noRun] [--fix] [--verbose] [--report-dir PATH]

From a fresh clone to a verified, runnable tokenusage2:
   1. Interpreter    find Python 3.14+ (override with PYTHON=/path/to/python)
   2. Virtualenv     create or reuse .venv
   3. Dependencies   install the project editable with the pinned dev tools
   4. Ruff lint      ruff check
   5. Ruff format    ruff format --check
   6. ShellCheck     this script, when shellcheck is installed
   7. Tests          pytest with a 95 % branch-coverage gate
   8. Smoke run      render one --demo frame
   9. Build          sdist and wheel into dist/
  10. Wheel check    install the wheel into a clean throwaway venv and run it
  11. Binary         .venv/bin/tokenusage2 reports the expected version
  12. Launch         start the live dashboard (skipped with --noRun or no TTY)

Every stage is timed; a summary and a verdict close the run. The exit status
is 0 only when every mandatory stage passed. Afterwards, run the dashboard
with .venv/bin/tokenusage2.

  --noRun        everything except launching the dashboard (what CI runs)
  --fix          apply ruff lint and format fixes before checking
  --verbose      stream every stage's output, not only the failing ones
  --report-dir   keep the stage logs there (default: a temporary directory,
                 kept only when a stage fails)
EOF
}

# --- output --------------------------------------------------------------------

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    readonly BOLD=$'\033[1m' CYAN=$'\033[1;36m' GREEN=$'\033[1;32m' RED=$'\033[1;31m'
    readonly YELLOW=$'\033[1;33m' DIM=$'\033[2m' RESET=$'\033[0m'
else
    readonly BOLD="" CYAN="" GREEN="" RED="" YELLOW="" DIM="" RESET=""
fi

colour_for() {
    case "$1" in
        PASS) printf '%s' "${GREEN}" ;;
        FAIL) printf '%s' "${RED}" ;;
        *) printf '%s' "${YELLOW}" ;;
    esac
}

now() {
    if [[ -n "${EPOCHREALTIME:-}" ]]; then
        printf '%s\n' "${EPOCHREALTIME/,/.}"
    else
        date +%s.%N
    fi
}

seconds_since() {
    awk -v start="$1" -v end="$(now)" 'BEGIN { printf "%.1f s", end - start }'
}

# capture NAME COMMAND... — run a command into LOG_DIR/NAME.log; on failure, or
# with --verbose, show its output.
capture() {
    local log="${LOG_DIR}/$1.log"
    shift
    if [[ "${VERBOSE}" == true ]]; then
        "$@" 2>&1 | tee "${log}"
        return "${PIPESTATUS[0]}"
    fi
    "$@" >"${log}" 2>&1
    local code=$?
    if [[ "${code}" -ne 0 ]]; then
        printf '  %s--- last lines of %s ---%s\n' "${DIM}" "${log}" "${RESET}"
        tail -n 40 "${log}" | sed 's/^/  | /'
    fi
    return "${code}"
}

record() {
    local name="$1" status="$2" took="$3" details="$4"
    SUMMARY+=("$(printf '%-13s %-4s %8s  %s' "${name}" "${status}" "${took}" "${details}")")
}

# run_stage NAME FUNCTION — time a mandatory stage. The function returns 0 to
# pass, 2 to skip (with a reason in DETAILS) and anything else to fail.
run_stage() {
    local name="$1" function="$2" start code status took
    printf '\n%s▶ %s%s\n' "${CYAN}" "${name}" "${RESET}"
    DETAILS=""
    start="$(now)"
    "${function}"
    code=$?
    took="$(seconds_since "${start}")"
    case "${code}" in
        0) status=PASS ;;
        2) status=SKIP ;;
        *) status=FAIL ;;
    esac
    if [[ "${status}" != SKIP ]]; then
        MANDATORY=$((MANDATORY + 1))
    fi
    if [[ "${status}" == PASS ]]; then
        PASSED=$((PASSED + 1))
    elif [[ "${status}" == FAIL ]]; then
        FAILED+=("${name}")
    fi
    record "${name}" "${status}" "${took}" "${DETAILS}"
    printf '  %s%s%s in %s  %s\n' "$(colour_for "${status}")" "${status}" "${RESET}" "${took}" \
        "${DETAILS}"
    [[ "${status}" != FAIL ]]
}

skip_stage() {
    record "$1" SKIP "" "$2"
}

# --- stages ------------------------------------------------------------------------

stage_interpreter() {
    local candidate path
    for candidate in "${PYTHON:-}" python3.14 python3; do
        [[ -n "${candidate}" ]] || continue
        path="$(command -v "${candidate}" 2>/dev/null)" || continue
        if "${path}" -c 'import sys; sys.exit(sys.version_info < (3, 14))' 2>/dev/null; then
            BASE_PYTHON="${path}"
            DETAILS="$("${path}" --version 2>&1) at ${path}"
            return 0
        fi
    done
    DETAILS="no Python 3.14+ found (set PYTHON=/path/to/python3.14)"
    return 1
}

stage_venv() {
    if [[ -x "${VENV_PYTHON}" ]]; then
        if "${VENV_PYTHON}" -c 'import sys; sys.exit(sys.version_info < (3, 14))'; then
            DETAILS="reused .venv ($("${VENV_PYTHON}" --version 2>&1))"
            return 0
        fi
        DETAILS=".venv runs $("${VENV_PYTHON}" --version 2>&1); delete .venv to rebuild it"
        return 1
    fi
    if ! capture venv "${BASE_PYTHON}" -m venv "${VENV_DIR}"; then
        DETAILS="could not create .venv"
        return 1
    fi
    DETAILS="created .venv ($("${VENV_PYTHON}" --version 2>&1))"
}

stage_dependencies() {
    local installer
    if command -v uv >/dev/null 2>&1; then
        installer=uv
        capture dependencies uv pip install --python "${VENV_PYTHON}" -e ".[dev]" || {
            DETAILS="uv pip install failed"
            return 1
        }
    else
        installer=pip
        if ! "${VENV_PYTHON}" -m pip --version >/dev/null 2>&1; then
            capture ensurepip "${VENV_PYTHON}" -m ensurepip --upgrade || {
                DETAILS=".venv has no pip and ensurepip failed"
                return 1
            }
        fi
        capture dependencies "${VENV_PYTHON}" -m pip install --disable-pip-version-check \
            -e ".[dev]" || {
            DETAILS="pip install failed"
            return 1
        }
    fi
    DETAILS="editable install via ${installer}; $("${VENV_PYTHON}" -m ruff --version),"
    DETAILS+=" $("${VENV_PYTHON}" -m pytest --version 2>&1 | head -n 1)"
}

stage_lint() {
    if [[ "${FIX}" == true ]]; then
        capture ruff-fix "${VENV_PYTHON}" -m ruff check --fix src tests scripts || true
    fi
    if capture ruff "${VENV_PYTHON}" -m ruff check src tests scripts; then
        DETAILS="no findings"
        return 0
    fi
    DETAILS="$(grep -E '^Found [0-9]+ error' "${LOG_DIR}/ruff.log" | tail -n 1)"
    DETAILS="${DETAILS:-see the ruff output} (--fix applies safe fixes)"
    return 1
}

stage_format() {
    if [[ "${FIX}" == true ]]; then
        capture ruff-format-fix "${VENV_PYTHON}" -m ruff format src tests scripts || true
    fi
    if capture ruff-format "${VENV_PYTHON}" -m ruff format --check src tests scripts; then
        DETAILS="$(tail -n 1 "${LOG_DIR}/ruff-format.log")"
        return 0
    fi
    DETAILS="$(grep -Eo '[0-9]+ files? would be reformatted' "${LOG_DIR}/ruff-format.log" |
        tail -n 1)"
    DETAILS="${DETAILS:-see the ruff output} (--fix reformats)"
    return 1
}

stage_shellcheck() {
    if ! command -v shellcheck >/dev/null 2>&1; then
        DETAILS="shellcheck is not installed"
        return 2
    fi
    if capture shellcheck shellcheck "${ROOT_DIR}/localPipeline.sh"; then
        DETAILS="localPipeline.sh is clean ($(shellcheck --version | sed -n 's/^version: //p'))"
        return 0
    fi
    DETAILS="findings in localPipeline.sh"
    return 1
}

stage_tests() {
    capture pytest "${VENV_PYTHON}" -m pytest -p no:cacheprovider --cov \
        --cov-report=term-missing:skip-covered --cov-report=xml \
        --cov-fail-under="${COVERAGE_GATE}"
    local code=$? result coverage
    result="$(grep -E '^=+ .*(passed|failed|error).* =+$' "${LOG_DIR}/pytest.log" | tail -n 1)"
    result="$(sed -E 's/^=+ | =+$//g' <<<"${result}")"
    coverage="$(grep -Eo 'Total coverage: [0-9.]+%' "${LOG_DIR}/pytest.log" | tail -n 1)"
    DETAILS="${result:-no pytest summary}; ${coverage:-no coverage total} (gate ${COVERAGE_GATE}%)"
    return "${code}"
}

stage_smoke() {
    if ! capture smoke "${VENV_PYTHON}" -m tokenusage2 --demo --once --color never --tz UTC \
        --width 120 --height 40; then
        DETAILS="the demo frame failed"
        return 1
    fi
    DETAILS="demo frame of $(wc -l <"${LOG_DIR}/smoke.log") lines rendered"
}

stage_build() {
    rm -rf "${ROOT_DIR}/dist"
    if ! capture build "${VENV_PYTHON}" -m build --outdir "${ROOT_DIR}/dist" "${ROOT_DIR}"; then
        DETAILS="the build failed"
        return 1
    fi
    DETAILS="$(find "${ROOT_DIR}/dist" -maxdepth 1 -type f -printf '%f\n' | sort | paste -sd ' ')"
}

stage_wheel() {
    local wheel check="${ROOT_DIR}/build/wheel-check" version
    wheel="$(find "${ROOT_DIR}/dist" -maxdepth 1 -name 'tokenusage2-*.whl' -print -quit)"
    if [[ -z "${wheel}" ]]; then
        DETAILS="no wheel in dist/"
        return 1
    fi
    rm -rf "${check}"
    if command -v uv >/dev/null 2>&1; then
        capture wheel-venv uv venv --quiet --python "${BASE_PYTHON}" "${check}" &&
            capture wheel-install uv pip install --python "${check}/bin/python" --no-deps "${wheel}"
    else
        capture wheel-venv "${BASE_PYTHON}" -m venv "${check}" &&
            capture wheel-install "${check}/bin/python" -m pip install \
                --disable-pip-version-check --no-deps "${wheel}"
    fi || {
        DETAILS="installing the wheel into a clean venv failed"
        return 1
    }
    version="$(cd "${check}" && "${check}/bin/tokenusage2" --version 2>&1)" || {
        DETAILS="the installed command failed: ${version}"
        return 1
    }
    if ! (cd "${check}" && capture wheel-run "${check}/bin/tokenusage2" --demo --once \
        --color never --tz UTC --width 100 --height 30); then
        DETAILS="the installed wheel cannot render a frame"
        return 1
    fi
    DETAILS="$(basename "${wheel}") → ${version}, renders from a clean venv"
}

stage_binary() {
    local expected actual
    expected="$("${VENV_PYTHON}" -c \
        'import runpy; print(runpy.run_path("src/tokenusage2/version.py")["__version__"])')"
    actual="$("${APP}" --version 2>&1)" || {
        DETAILS=".venv/bin/tokenusage2 is missing or broken"
        return 1
    }
    if [[ "${actual}" != "tokenusage2 ${expected}" ]]; then
        DETAILS="reports '${actual}', expected ${expected}"
        return 1
    fi
    DETAILS=".venv/bin/tokenusage2 → ${actual}"
}

# --- driver ------------------------------------------------------------------------

parse_arguments() {
    while (($#)); do
        case "$1" in
            --noRun) RUN_APP=false ;;
            --fix) FIX=true ;;
            --verbose) VERBOSE=true ;;
            --report-dir)
                if [[ $# -lt 2 || -z "$2" ]]; then
                    printf 'error: --report-dir needs a path\n' >&2
                    usage >&2
                    exit 2
                fi
                REPORT_DIR="$2"
                shift
                ;;
            -h | --help)
                usage
                exit 0
                ;;
            *)
                printf 'unknown option: %s\n' "$1" >&2
                usage >&2
                exit 2
                ;;
        esac
        shift
    done
}

cleanup() {
    if [[ "${REMOVE_LOG_DIR}" == true && ${#FAILED[@]} -eq 0 ]]; then
        rm -rf "${LOG_DIR}"
    elif [[ -d "${LOG_DIR}" ]]; then
        printf 'stage logs: %s\n' "${LOG_DIR}"
    fi
}

prepare_logs() {
    if [[ -n "${REPORT_DIR}" ]]; then
        mkdir -p "${REPORT_DIR}"
        LOG_DIR="$(cd -- "${REPORT_DIR}" && pwd)"
        REMOVE_LOG_DIR=false
    else
        LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/tokenusage2-pipeline.XXXXXX")"
    fi
    trap cleanup EXIT
}

print_summary() {
    local launch="$1" total line status verdict report
    total="$(seconds_since "${PIPELINE_START}")"
    record "Launch" "$([[ "${launch}" == next ]] && echo NEXT || echo SKIP)" "" \
        "$([[ "${launch}" == next ]] && echo "starting .venv/bin/tokenusage2" || echo "${launch}")"
    if [[ ${#FAILED[@]} -eq 0 ]]; then
        verdict="VERDICT: PASS — ${PASSED} of ${MANDATORY} stages passed in ${total}"
        verdict+="; run .venv/bin/tokenusage2"
    else
        verdict="VERDICT: FAIL — failed: ${FAILED[*]} (${PASSED} of ${MANDATORY} passed, ${total})"
    fi
    report="$(
        printf '%s━━━━━━━━━━━━━━━━━━━━━━ tokenUsage2 local pipeline ━━━━━━━━━━━━━━━━━━━━━━%s\n' \
            "${BOLD}" "${RESET}"
        printf '%s%-13s %-4s %8s  %s%s\n' "${DIM}" "stage" "" "time" "details" "${RESET}"
        for line in "${SUMMARY[@]}"; do
            status="${line:14:4}"
            printf '%s%s%s%s%s\n' "${line:0:14}" "$(colour_for "${status}")" "${status}" "${RESET}" \
                "${line:18}"
        done
        printf '%s\n' "────────────────────────────────────────────────────────────────────────"
        if [[ ${#FAILED[@]} -eq 0 ]]; then
            printf '%s%s%s\n' "${GREEN}" "${verdict}" "${RESET}"
        else
            printf '%s%s%s\n' "${RED}" "${verdict}" "${RESET}"
        fi
    )"
    printf '\n%s\n' "${report}"
    # The same table without colours, for CI job summaries and --report-dir; the
    # escape sequences need a regex, which parameter expansion cannot express.
    # shellcheck disable=SC2001
    sed 's/\x1b\[[0-9;]*m//g' <<<"${report}" >"${LOG_DIR}/summary.txt"
}

main() {
    parse_arguments "$@"
    cd -- "${ROOT_DIR}" || exit 1
    prepare_logs
    PIPELINE_START="$(now)"
    printf '%stokenUsage2 local pipeline%s — %s\n' "${BOLD}" "${RESET}" \
        "$(git -C "${ROOT_DIR}" describe --always --dirty 2>/dev/null || echo 'no git')"

    local ready=false gates=true built=false entry launch
    if run_stage "Interpreter" stage_interpreter; then
        if run_stage "Virtualenv" stage_venv; then
            run_stage "Dependencies" stage_dependencies && ready=true
        else
            skip_stage "Dependencies" "no usable .venv"
        fi
    else
        skip_stage "Virtualenv" "no Python 3.14+"
        skip_stage "Dependencies" "no Python 3.14+"
    fi

    for entry in "Ruff lint:stage_lint" "Ruff format:stage_format" "ShellCheck:stage_shellcheck" \
        "Tests:stage_tests" "Smoke run:stage_smoke"; do
        if [[ "${ready}" == true ]]; then
            run_stage "${entry%%:*}" "${entry#*:}" || gates=false
        else
            skip_stage "${entry%%:*}" "the dependencies are not installed"
        fi
    done

    if [[ "${ready}" == true && "${gates}" == true ]]; then
        run_stage "Build" stage_build && built=true
    else
        skip_stage "Build" "an earlier stage failed"
    fi
    if [[ "${built}" == true ]]; then
        run_stage "Wheel check" stage_wheel
    else
        skip_stage "Wheel check" "no fresh build"
    fi
    if [[ "${ready}" == true ]]; then
        run_stage "Binary" stage_binary
    else
        skip_stage "Binary" "the dependencies are not installed"
    fi

    if [[ ${#FAILED[@]} -gt 0 ]]; then
        launch="a mandatory stage failed"
    elif [[ "${RUN_APP}" != true ]]; then
        launch="--noRun"
    elif [[ ! -t 0 || ! -t 1 ]]; then
        launch="no interactive terminal"
    else
        launch=next
    fi
    print_summary "${launch}"

    if [[ ${#FAILED[@]} -gt 0 ]]; then
        exit 1
    fi
    if [[ "${launch}" == next ]]; then
        cleanup
        trap - EXIT
        exec "${APP}"
    fi
    exit 0
}

main "$@"
