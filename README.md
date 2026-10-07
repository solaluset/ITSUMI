# Is That Still Up? Monitor It!

Minimalistic monitoring framework

## Running

1. Install dependencies: `pip install -r requirements.txt`
2. Run the web server: `fastapi run`

See the `/docs` endpoint for HTTP API details.

## Configuration

If `ITSUMI_WORKDIR` environment variable is set, it is used as root for all paths.
Otherwise current working directory is used.

`data` folder is used to store internal data (currently just SQLite database).

Config files reside in the `config` directory:

  - `main.yml` provides global settings
  - `runtimes.yml` provides runtimes (commands) for checks and reporters
  - `checks.yml` configures periodic checks
  - `reporters.yml` configures tasks to run when a check enters failed state

A task is considered successful if it has exit code 0
