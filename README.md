# Fingrid Dataset Viewer

Small Python project for exploring Fingrid datasets and testing dataset API calls.

## Files

- `fingrid_dataset_viewer.py`: local web viewer that lists all available Fingrid datasets.
- `fg.py`: simple `requests` example for dataset data.
- `fg2.py`: simple `urllib` example for dataset data.

## Setup

1. Create or activate the virtual environment.
2. Set your Fingrid API key:

```zsh
export FINGRID_API_KEY='your_api_key_here'
```

3. Start the viewer:

```zsh
/Users/pekkakosonen/Documents/code/fingrid/.venv/bin/python /Users/pekkakosonen/Documents/code/fingrid/fingrid_dataset_viewer.py
```

4. Open the local URL printed by the script, usually `http://127.0.0.1:8000` or the next available port.

## Deployment

### Vercel

This project is configured for Vercel's serverless Python platform. To deploy:

1. Push changes to GitHub.
2. Vercel auto-deploys from the repository.
3. Set the `FINGRID_API_KEY` environment variable in Vercel project settings.

The Flask app in `api/index.py` serves the viewer at the root path `/`.

### Local

Run the Flask app:

```zsh
export FINGRID_API_KEY='your_api_key_here'
python -m flask --app api/index run
```

Or use the original standalone server:

```zsh
/Users/pekkakosonen/Documents/code/fingrid/.venv/bin/python /Users/pekkakosonen/Documents/code/fingrid/fingrid_dataset_viewer.py
```

## GitHub workflow

This repository is intended to stay committed and pushed regularly so changes are easy to revert.