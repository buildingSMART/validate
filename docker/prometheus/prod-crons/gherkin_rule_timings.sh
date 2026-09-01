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
  echo "# HELP gherkin_rule_cpu_seconds_total Totale CPU-tijd per gherkin-regel (uit de logs, cumulatief over alle runs)."
  echo "# TYPE gherkin_rule_cpu_seconds_total counter"
  echo "# HELP gherkin_rule_runs_total Aantal keren dat de regel is uitgevoerd."
  echo "# TYPE gherkin_rule_runs_total counter"
  echo "# HELP gherkin_rule_cpu_seconds_max Langste enkele run van deze regel (CPU-seconden)."
  echo "# TYPE gherkin_rule_cpu_seconds_max gauge"
  echo "# HELP gherkin_rule_cpu_seconds_avg Gemiddelde CPU-tijd per run."
  echo "# TYPE gherkin_rule_cpu_seconds_avg gauge"

  # B1-uitbreiding (2/8): de logregel kan sinds de per-regel-geheugenmeting eindigen op
  # " Peak RSS: <n> MB (delta <+/-n> MB)." — veld 3/4 zijn dan gevuld, anders leeg.
  # find|xargs i.p.v. glob: bij ~100k logbestanden overschrijdt "$LOG_DIR"/*.log
  # de ARG_MAX-limiet (~2 MB) en faalt grep met "Argument list too long".
  find "$LOG_DIR" -maxdepth 1 -name '*.log' -print0 2>/dev/null \
    | xargs -0 -r grep -h "Elapsed process time" \
    | sed -E "s/.*Feature '([^']+)'.*time: ([0-9.]+) seconds\.( Peak RSS: ([0-9]+) MB \(delta ([+-][0-9]+) MB\)\.)?.*/\2\t\1\t\4\t\5/" \
    | awk -F'\t' '
        {
          # regelcode = eerste woord vóór de spatie-streepje-spatie (bv. "CTX000 - ...")
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

  # --- Per-maand serie (conferentie/trend: "did our efforts help?") ---------
  # De tijdas kan niet als echte historie de TSDB in (de textfile collector
  # weigert client-side timestamps), dus de maand zit als label. Maand = mtime
  # van het logbestand: het moment van de run, niet van de codewijziging.
  # Cardinaliteit: ~150 regels x aantal maanden; alleen maanden met runs
  # krijgen een serie. Let op bij interpretatie: _avg is de eerlijke maat voor
  # trends, _cpu_seconds volgt vooral het uploadvolume.
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

  echo "# HELP gherkin_rule_timings_logfiles Aantal logbestanden dat is ingelezen."
  echo "# TYPE gherkin_rule_timings_logfiles gauge"
  echo "gherkin_rule_timings_logfiles $(find "$LOG_DIR" -maxdepth 1 -name '*.log' 2>/dev/null | wc -l)"
} > "$TMP"

# atomisch vervangen, zodat node_exporter nooit een half bestand leest
mv "$TMP" "$OUT"
chmod 644 "$OUT"
