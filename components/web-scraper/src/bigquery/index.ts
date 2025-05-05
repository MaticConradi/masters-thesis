import { BigQuery } from '@google-cloud/bigquery';

export const bigquery = new BigQuery({ projectId: "personal-sandbox-403414" });

export const dataset = bigquery.dataset("mc_magistrska");
export const articlesTable = dataset.table("articles");