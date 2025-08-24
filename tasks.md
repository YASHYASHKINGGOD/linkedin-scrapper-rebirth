# tasks.md
## Backlog
- [ ] Migrate linkedin_links: url → TEXT; add url_canonical (lower(url)) GENERATED; unique index on url_canonical (acceptance: migration applies without data loss)
- [ ] Add import-and-backup command to CLI for atomic upsert + CSV backup (acceptance: backup CSV written with newly inserted rows)
- [ ] Add link_provenance table and write on insert/update (acceptance: provenance rows visible for a sample)
- [ ] Create dashboards for ingest/classify/scrape/extract queues (acceptance: live metrics visible)
- [ ] Add ON CONFLICT upsert path in DB importer with canonical URL (acceptance: duplicates deduped)
- [ ] Implement scheduler to run ingest every 10m; nightly backup export to cloud (acceptance: jobs execute on schedule)
## In Progress
- [ ] <task>
## Done
- [x] <task> (#commit or link)
## Bugs
- [ ] repro: … | expected: … | logs: …
