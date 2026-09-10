# ForecastGuard

Reliable end-to-end sales forecasting pipeline built with Airflow,
dbt, PostgreSQL and Python.

ForecastGuard focuses on a common ML engineering problem:
a forecasting model is only as reliable as the data pipeline feeding it.

## Architecture

orders.csv
|
v
Airflow
|
v
PostgreSQL
|
v
dbt
|
v
Data Quality
|
v
Forecasting
|
v
LLM Assistant

## Status

V1 under development
