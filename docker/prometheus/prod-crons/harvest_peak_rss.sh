#!/bin/bash
# Harvests "Peak RSS for" lines from the validate_worker service logs into a
# persistent, deduplicated file -- container logs are lost on redeploy, this
# file is not. Cron: every 10 min. Override OUT via env prefix in the cron
# line (PROD: OUT=/data/srv/perf-collected/peak_rss.log).
#
# The harvested file is also aggregated into Prometheus metrics for the
# node_exporter textfile collector, so peak RSS is graphable and alertable
# instead of only greppable. Set TEXTFILE_DIR in the cron line to enable it
# (PROD: TEXTFILE_DIR=/data/srv/textfile), same as gherkin_rule_timings.sh.
OUT=${OUT:?set OUT to the harvested log file, e.g. OUT=/data/srv/perf-collected/peak_rss.log}
mkdir -p "$(dirname "$OUT")"
TMP=$(mktemp)
timeout 100 docker service logs validate_worker --since 30m 2>&1 | grep "Peak RSS for" >> "$OUT" 2>/dev/null
sort -u "$OUT" > "$TMP" && mv "$TMP" "$OUT"

TEXTFILE_DIR=${TEXTFILE_DIR:?set TEXTFILE_DIR to the node_exporter textfile directory, e.g. TEXTFILE_DIR=/data/srv/textfile}
PROM="$TEXTFILE_DIR/peak_rss.prom"
PROM_TMP="$PROM.$$.tmp"
mkdir -p "$TEXTFILE_DIR"

# Source line (check_programs.py):
#   Peak RSS for <SUBTASK> subprocess (task #<id>): <n> kB (min MemAvailable ...)
# Every run recomputes from the full harvested file -- no incremental state, so
# a one-off manual run backfills the whole history. "Last" is keyed on the task
# id rather than file order, because the dedup above sorts lexically and the
# newest line is therefore not the last one.
{
  sed -nE 's/.*Peak RSS for ([A-Z_]+) subprocess \(task #([0-9]+)\): ([0-9]+) kB.*/\1\t\2\t\3/p' "$OUT" \
  | awk -F'\t' '
      {
        t = $1; id = $2 + 0; v = $3 + 0;
        if (!(t in n)) order[++k] = t;
        n[t]++; sum[t] += v;
        if (v > mx[t]) mx[t] = v;
        if (id > lastid[t]) { lastid[t] = id; last[t] = v }
        if (v > gmax) gmax = v;
        total++;
      }
      END {
        print "# HELP peak_rss_subtask_max_kb Highest peak RSS observed per subtask type (from harvested worker logs).";
        print "# TYPE peak_rss_subtask_max_kb gauge";
        for (i = 1; i <= k; i++) printf "peak_rss_subtask_max_kb{subtask=\"%s\"} %d\n", order[i], mx[order[i]];

        print "# HELP peak_rss_subtask_avg_kb Average peak RSS per subtask type over all harvested samples.";
        print "# TYPE peak_rss_subtask_avg_kb gauge";
        for (i = 1; i <= k; i++) printf "peak_rss_subtask_avg_kb{subtask=\"%s\"} %.0f\n", order[i], sum[order[i]] / n[order[i]];

        print "# HELP peak_rss_subtask_last_kb Peak RSS of the most recent observed run per subtask type (highest task id).";
        print "# TYPE peak_rss_subtask_last_kb gauge";
        for (i = 1; i <= k; i++) printf "peak_rss_subtask_last_kb{subtask=\"%s\"} %d\n", order[i], last[order[i]];

        print "# HELP peak_rss_subtask_samples Number of harvested samples per subtask type.";
        print "# TYPE peak_rss_subtask_samples gauge";
        for (i = 1; i <= k; i++) printf "peak_rss_subtask_samples{subtask=\"%s\"} %d\n", order[i], n[order[i]];

        print "# HELP peak_rss_observed_max_kb Highest peak RSS observed across all subtask types.";
        print "# TYPE peak_rss_observed_max_kb gauge";
        printf "peak_rss_observed_max_kb %d\n", gmax;

        print "# HELP peak_rss_samples Total number of harvested samples.";
        print "# TYPE peak_rss_samples gauge";
        printf "peak_rss_samples %d\n", total + 0;
      }'

  # Lets a panel or alert tell "quiet" apart from "the harvester stopped running".
  echo "# HELP peak_rss_harvest_timestamp_seconds Unix time of the last harvest run."
  echo "# TYPE peak_rss_harvest_timestamp_seconds gauge"
  echo "peak_rss_harvest_timestamp_seconds $(date +%s)"
} > "$PROM_TMP"

# atomically replace, so node_exporter never reads a half-written file
mv "$PROM_TMP" "$PROM"
chmod 644 "$PROM"
