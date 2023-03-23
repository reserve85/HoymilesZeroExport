# Changelog
## V1.10
### Script
* Bugfix for openDTU set limit, missing array index
## V1.9
### Script
* Add: SHRDZM Powermeter Interface 
* Add: an optional function CutLimitToProduction: prevents the setpoint from running away... 
* Changed: logging to ./log/daily.log, creates a new logfile on midnight
### Config
* Add: Section `[SHRDZM]` + `USE_SHRDZM` in Config (default disabled)
* Add: `MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER` (default disabled)
* Add: `ENABLE_LOG_TO_FILE` and `LOG_BACKUP_COUNT` (default disabled)
* Add: VERSION information
