# Website Image Downloader

A production-quality Python tool that crawls a website, downloads all product/book images, converts them to **JPG** (or WebP), and organises them into folders named after each page title.

---

## Features

- **Playwright** browser — works on JS-rendered and static HTML sites
- **BeautifulSoup4 + lxml** for robust HTML parsing
- **Lazy-load aware** — reads `data-src`, `data-lazy-src`, `data-original`
- **Smart filtering** — skips logos, icons, SVGs, and tiny images
- **Cover detection** — saves the primary image as `cover.jpg`
- **Retry logic** — 3 attempts per image before giving up
- **Duplicate guard** — never downloads the same URL twice
- **Progress bar** via tqdm
- **CSV summary report** on completion
- **Fully configurable** — one file (`config.py`) controls everything

---

## Project Structure

```
website-image-downloader/
├── app.py            # Entry point — run this
├── config.py         # All settings (START_URL, quality, threads, etc.)
├── crawler.py        # Discovers product/book page URLs
├── scraper.py        # Extracts title + image URLs from each page
├── downloader.py     # Downloads images with retry logic
├── converter.py      # Converts images to JPG (or WebP) via Pillow
├── utils.py          # Shared helpers (logging, sanitization, etc.)
├── requirements.txt
├── output/           # All downloaded images land here
└── logs/             # Debug log file created at runtime
```

---

## Installation

### 1. Clone / download the project

```bash
git clone https://github.com/yourname/website-image-downloader.git
cd website-image-downloader
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install the Playwright browser

```bash
playwright install chromium
```

---

## Configuration

Open **`config.py`** and set at minimum:

```python
START_URL = "https://books.toscrape.com/"   # ← point this at your target site
OUTPUT_FORMAT = "jpg"                        # "jpg" or "webp"
JPG_QUALITY = 90                             # 0–100
```

Other options you can tune:

| Setting | Default | Description |
|---|---|---|
| `OUTPUT_FOLDER` | `"output"` | Root folder for downloads |
| `MAX_THREADS` | `4` | Parallel download threads |
| `CRAWL_DELAY_SECONDS` | `0.5` | Politeness delay between pages |
| `MAX_RETRIES` | `3` | Retry attempts per failed image |
| `MIN_IMAGE_SIZE_PX` | `100` | Skip images smaller than this |
| `HEADLESS` | `True` | Show/hide browser window |

---

## Usage

```bash
python app.py
```

### Example output

```
🔍  Discovering product pages …
✅  Found 1000 product pages.

Books processed: ██████████░░░░░░ 52/1000

🎉  Done in 183.4s
    Pages processed : 1000
    Images saved    : 1842
    Report          : output/download_report.csv
    Output folder   : /home/user/website-image-downloader/output
```

### Folder structure created

```
output/
├── Atomic Habits/
│   ├── cover.jpg
│   ├── image-1.jpg
│   └── image-2.jpg
├── Deep Work/
│   ├── cover.jpg
│   └── image-1.jpg
├── download_report.csv
└── ...
```

### CSV report

```csv
Book Name,Images Downloaded
Atomic Habits,3
Deep Work,2
Psychology of Money,4
```

---

## Adapting to a Different Website

1. Change `START_URL` in `config.py`.
2. If pagination uses a different pattern, extend `_find_next_page_url()` in `crawler.py`.
3. If product links have unusual URL structures, adjust `PRODUCT_PATH_SIGNALS` in `crawler.py`.
4. If images are inside non-standard containers, add selectors to `_extract_image_urls()` in `scraper.py`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| No product URLs found | Check `START_URL`; adjust path signals in `crawler.py` |
| 0 images on every page | Add the site's image container selectors to `scraper.py` |
| Playwright not found | Run `playwright install chromium` |
| Images too small / filtered | Lower `MIN_IMAGE_SIZE_PX` in `config.py` |
| Slow crawl | Increase `MAX_THREADS`; decrease `CRAWL_DELAY_SECONDS` |

Full debug log is written to `logs/downloader.log` after every run.

---

## License

MIT — free to use and modify.
