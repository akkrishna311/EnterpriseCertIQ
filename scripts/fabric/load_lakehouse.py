# Fabric notebook — load the EnterpriseCertIQ ontology CSVs into Lakehouse Delta tables.
#
# HOW TO RUN (Path A, easiest — runs in-capacity as your identity, no local auth):
#   1. Run `python scripts/export_fabric_tables.py` locally → backend/data/fabric_export/*.csv
#   2. In your Fabric workspace, open the Lakehouse → Files → upload the whole
#      `fabric_export` folder (so files land at  Files/fabric_export/*.csv ).
#   3. Create a Notebook, attach it to that Lakehouse, paste this file into a cell, Run all.
#
# It overwrites the tables every run, so re-loading after you edit the local JSON is
# idempotent — that's the "keep Azure in sync with local" loop.

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

# Folder where you uploaded the exported CSVs (relative to the attached Lakehouse).
SRC = "Files/fabric_export"

# CSV file  →  Delta table name
TABLES = {
    "certifications.csv":        "certifications",
    "cert_domains.csv":          "cert_domains",
    "cert_domain_services.csv":  "cert_domain_services",
    "cert_advancement.csv":      "cert_advancement",
    "learners.csv":              "learners",
    "learner_evidence.csv":      "learner_evidence",
    "learner_work_signals.csv":  "learner_work_signals",
    "teams.csv":                 "teams",
    "team_members.csv":          "team_members",
    "team_cert_targets.csv":     "team_cert_targets",
    "cohort_outcomes.csv":       "cohort_outcomes",
}

for csv_name, table in TABLES.items():
    df = (
        spark.read
        .option("header", "true")
        .option("inferSchema", "true")
        .csv(f"{SRC}/{csv_name}")
    )
    # Managed Delta table in the Lakehouse; overwrite makes re-loads idempotent.
    df.write.format("delta").mode("overwrite").saveAsTable(table)
    print(f"loaded {table:<24} {df.count():>3} rows, {len(df.columns)} cols")

print("Done. Tables are now bindable in the Fabric IQ ontology.")
