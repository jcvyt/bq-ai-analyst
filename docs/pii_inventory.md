This is the senior-level insight of the day: DLP finds direct identifiers, but it does not reliably classify quasi-identifiers. Columns like postal_code, age, gender, and lat/long are each harmless alone but re-identifying in combination. A person has to classify those, and you should say so explicitly. That human classification is what turns a scan into a governance artifact.

Fill in the DLP column from your actual results. The rest is a starting point; confirm it against the schema:

Table.column	DLP infoType	Class	Semantic-layer rule
users.email	EMAIL_ADDRESS	Direct identifier	Exclude
users.first_name, last_name	FIRST/LAST_NAME	Direct identifier	Exclude
users.street_address	STREET_ADDRESS	Direct identifier	Exclude
users.latitude, longitude, user_geom, postal_code	(likely none)	Quasi-identifier	Exclude
users.city	(likely none)	Quasi-identifier	Aggregate-only
users.state, country	—	Low-risk geography	Allow
users.age, gender	—	Quasi-identifier	Aggregate-only, age as bands
events.ip_address	IP_ADDRESS	Direct identifier	Exclude
events.city, state, postal_code	—	Quasi-identifier	Same rules as users
*.user_id	—	Pseudonymous key	Join key only, never projected

Policy rule for the capstone: any aggregate the agent returns over users must suppress groups with fewer than 10 distinct users. Write that down now. It becomes a testable guardrail and one of your golden eval questions in Phase 2.

Leave column-level security (policy tags) for Phase 2. You’ll add it on curated once that layer exists.