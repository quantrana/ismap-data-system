"""ETL (Extract-Transform-Load) pipeline package for ISMAP.

This package contains the components used by AWS Glue jobs and local
batch processes to orchestrate the full retail analytics pipeline:

* `pipeline` orchestrates overall ETL flows.
* `validate` provides data quality checks and schema validation.
* `transform` houses feature engineering and business logic.
* `load` manages loading curated data into the PostgreSQL warehouse.
"""

