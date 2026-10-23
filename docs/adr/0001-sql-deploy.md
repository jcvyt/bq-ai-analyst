	Scripted DDL in CI (bq query as sa-tf-ci)	Dataform
New principals	None; reuses sa-tf-ci (already accepted risk)	Dataform SA needs READER on raw. That’s a new raw reader: re-run Policy Analyzer and update the inventory.
Dependency order	You hand-roll it	Built-in DAG
Tests	Your pytest access tests	Assertions + your tests
Enterprise signal	Low	High (GCP-native, common in job specs)
Unknown	—	Whether it cleanly expresses the aggregation-threshold analysis rule on views, and whether authorized-view grants survive its CREATE OR REPLACE