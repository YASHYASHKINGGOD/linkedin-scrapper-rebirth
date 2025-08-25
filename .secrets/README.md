# Local-only secrets. DO NOT COMMIT real secrets to version control.
# This folder is already in .gitignore.
# You can store LinkedIn credentials in either of these formats:
#
# 1) JSON: linkedin.json
#    {
#      "LI_EMAIL": "your_email",
#      "LI_PASSWORD": "your_password"
#    }
#
# 2) ENV: linkedin.env
#    LI_EMAIL=your_email
#    LI_PASSWORD=your_password
#
# The scraper will prefer environment variables if set, otherwise it will
# read from these local files at runtime.

