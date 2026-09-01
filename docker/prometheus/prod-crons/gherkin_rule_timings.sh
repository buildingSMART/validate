#!/bin/bash
# Aggregates per-rule cost from the gherkin runner logs into Prometheus metrics
# for the node_exporter textfile collector. Cron: nightly.
#
# Source: $LOG_DIR/*.log -- "Elapsed process time" lines (CPU time, not wall
#   clock) with optional "Peak RSS ... (delta ...)" suffix since the B1 change.
# Output: $TEXTFILE_DIR/gherkin_rules.prom (written atomically).
# Every run rescans ALL logs and recomputes the counters -- no incremental
# state; a one-off manual run therefore fills the panel with full history.
set -uo pipefail

LOG_DIR=${LOG_DIR:-/srv/nfs/gherkin_logs}
TEXTFILE_DIR=${TEXTFILE_DIR:?set TEXTFILE_DIR to the node_exporter textfile directory, e.g. TEXTFILE_DIR=/data/srv/textfile}
OUT="$TEXTFILE_DIR/gherkin_rules.prom"
TMP="$OUT.$$.tmp"

mkdir -p "$TEXTFILE_DIR"

{
  echo "# HELP gherkin_rule_cpu_seconds_total Total CPU time per gherkin rule (from the logs, cumulative over all runs)."
  echo "# TYPE gherkin_rule_cpu_seconds_total counter"
  echo "# HELP gherkin_rule_runs_total Number of times the rule was executed."
  echo "# TYPE gherkin_rule_runs_total counter"
  echo "# HELP gherkin_rule_cpu_seconds_max Longest single run of this rule (CPU seconds)."
  echo "# TYPE gherkin_rule_cpu_seconds_max gauge"
  echo "# HELP gherkin_rule_cpu_seconds_avg Average CPU time per run."
  echo "# TYPE gherkin_rule_cpu_seconds_avg gauge"

  # Since the per-rule memory measurement (B1, Aug 2) a log line may end with
  # " Peak RSS: <n> MB (delta <+/-n> MB)." - fields 3/4 are then filled, else empty.
  # find|xargs instead of a glob: with ~100k log files "$LOG_DIR"/*.log exceeds
  # the ARG_MAX limit (~2 MB) and grep fails with "Argument list too long".
  find "$LOG_DIR" -maxdepth 1 -name '*.log' -print0 2>/dev/null \
    | xargs -0 -r grep -h "Elapsed process time" \
    | sed -E "s/.*Feature '([^']+)'.*time: ([0-9.]+) seconds\.( Peak RSS: ([0-9]+) MB \(delta ([+-][0-9]+) MB\)\.)?.*/\2\t\1\t\4\t\5/" \
    | awk -F'\t' '
        {
          # rule code = first word before the " - " separator (e.g. "CTX000 - ...")
          split($2, parts, " ");
          rule = parts[1];
          gsub(/[^A-Za-z0-9_]/, "", rule);
          if (rule == "") next;
          sum[rule] += $1; n[rule]++;
          if ($1 > mx[rule]) mx[rule] = $1;
          if ($3 != "") { memn[rule]++; memsum[rule] += $3; if ($3 > memmx[rule]) memmx[rule] = $3;
                          dsum[rule] += $4; if ($4 > dmx[rule]) dmx[rule] = $4; }
        }
        END {
          for (r in sum) {
            printf "gherkin_rule_cpu_seconds_total{rule=\"%s\"} %.2f\n", r, sum[r];
            printf "gherkin_rule_runs_total{rule=\"%s\"} %d\n", r, n[r];
            printf "gherkin_rule_cpu_seconds_max{rule=\"%s\"} %.2f\n", r, mx[r];
            printf "gherkin_rule_cpu_seconds_avg{rule=\"%s\"} %.3f\n", r, sum[r]/n[r];
            if (memn[r] > 0) {
              printf "gherkin_rule_peak_rss_mb_max{rule=\"%s\"} %d\n", r, memmx[r];
              printf "gherkin_rule_peak_rss_mb_avg{rule=\"%s\"} %.1f\n", r, memsum[r]/memn[r];
              printf "gherkin_rule_delta_mb_max{rule=\"%s\"} %d\n", r, dmx[r];
              printf "gherkin_rule_delta_mb_avg{rule=\"%s\"} %.1f\n", r, dsum[r]/memn[r];
              printf "gherkin_rule_mem_samples_total{rule=\"%s\"} %d\n", r, memn[r];
            }
          }
        }'

  # --- Per-month series (trend: "did our efforts help?") -------------------
  # The time axis cannot go into the TSDB as real history (the textfile
  # collector rejects client-side timestamps), so the month is a label.
  # Month = mtime of the log file: the moment of the run, not of the code
  # change. Cardinality: ~150 rules x number of months; only months with runs
  # get a series. When reading: _avg is the honest measure for trends,
  # _cpu_seconds mostly follows upload volume.
  echo "# HELP gherkin_rule_monthly_cpu_seconds Total CPU seconds per rule per calendar month (month = log file mtime)."
  echo "# TYPE gherkin_rule_monthly_cpu_seconds gauge"
  echo "# HELP gherkin_rule_monthly_runs Number of runs per rule per calendar month."
  echo "# TYPE gherkin_rule_monthly_runs gauge"
  echo "# HELP gherkin_rule_monthly_cpu_seconds_avg Average CPU seconds per run, per rule per calendar month."
  echo "# TYPE gherkin_rule_monthly_cpu_seconds_avg gauge"

  MONTHMAP=$(mktemp)
  find "$LOG_DIR" -maxdepth 1 -name '*.log' -printf '%p\t%TY-%Tm\n' 2>/dev/null > "$MONTHMAP"
  find "$LOG_DIR" -maxdepth 1 -name '*.log' -print0 2>/dev/null \
    | xargs -0 -r grep -H "Elapsed process time" \
    | sed -E "s/^([^:]+):.*Feature '([^']+)'.*time: ([0-9.]+) seconds\..*/\1\t\2\t\3/" \
    | awk -F'\t' -v monthmap="$MONTHMAP" '
        BEGIN { while ((getline line < monthmap) > 0) { split(line, a, "\t"); mm[a[1]] = a[2] } }
        {
          split($2, parts, " ");
          rule = parts[1];
          gsub(/[^A-Za-z0-9_]/, "", rule);
          if (rule == "" || !($1 in mm)) next;
          key = rule SUBSEP mm[$1];
          sum[key] += $3; n[key]++;
        }
        END {
          for (k in sum) {
            split(k, p, SUBSEP);
            printf "gherkin_rule_monthly_cpu_seconds{rule=\"%s\",month=\"%s\"} %.2f\n", p[1], p[2], sum[k];
            printf "gherkin_rule_monthly_runs{rule=\"%s\",month=\"%s\"} %d\n", p[1], p[2], n[k];
            printf "gherkin_rule_monthly_cpu_seconds_avg{rule=\"%s\",month=\"%s\"} %.3f\n", p[1], p[2], sum[k]/n[k];
          }
        }'
  rm -f "$MONTHMAP"

  echo "# HELP gherkin_rule_timings_logfiles Number of log files read."
  echo "# TYPE gherkin_rule_timings_logfiles gauge"
  echo "gherkin_rule_timings_logfiles $(find "$LOG_DIR" -maxdepth 1 -name '*.log' 2>/dev/null | wc -l)"
} > "$TMP"

# replace atomically, so node_exporter never reads a half-written file
mv "$TMP" "$OUT"
chmod 644 "$OUT"
