import httpx
import img2pdf
import os
import tempfile
import asyncio
import logging
import json
import subprocess
import sys
from pathlib import Path
from PIL import Image

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

async def download_image(client, url, path):
    try:
        response = await client.get(url, timeout=15.0)
        response.raise_for_status()
        with open(path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        logger.warning(f"Failed to download {url}: {e}")
        return False

async def download_fliphtml5(book_id: str, output_path: str):
    if "online.fliphtml5.com/" in book_id:
        book_id = book_id.split("online.fliphtml5.com/")[-1].strip("/")
    
    book_id = book_id.strip("/")
    logger.info(f"Target Book ID: {book_id}")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Fetch Config
        possible_paths = ["config.js", "javascript/config.js"]
        config_content = None
        
        async with httpx.AsyncClient() as client:
            for suffix in possible_paths:
                url = f"http://online.fliphtml5.com/{book_id}/{suffix}"
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    config_content = resp.text
                    logger.info(f"Fetched config from {suffix}")
                    break
                except:
                    pass
        
        if not config_content:
            logger.error("Could not find configuration file.")
            return

        config_path = os.path.join(temp_dir, "config.js")
        with open(config_path, "w") as f:
            f.write(config_content)

        # Run Node Decoder
        decoder_script = Path("fliphtml5_decoder.js").absolute()
        if not decoder_script.exists():
            logger.error("fliphtml5_decoder.js not found in current directory.")
            return

        logger.info("Running WASM decoder...")
        try:
            result = subprocess.run(
                ["node", str(decoder_script), config_path],
                capture_output=True, text=True, check=True
            )
            raw_json = result.stdout.strip()
            # Clean preamble
            start = raw_json.find('{')
            end = raw_json.rfind('}')
            if start != -1 and end != -1:
                raw_json = raw_json[start:end+1]
            
            book_data = json.loads(raw_json)
        except Exception as e:
            logger.error(f"Decoding failed: {e}")
            if hasattr(e, 'stderr'): logger.error(e.stderr)
            return

        # Parse Pages
        pages = book_data.get('fliphtml5_pages') or book_data.get('pages')
        if not pages:
             # Fallback search
             for v in book_data.values():
                 if isinstance(v, list) and v and isinstance(v[0], dict) and 'n' in v[0]:
                     pages = v
                     break
        
        if not pages:
            logger.error("No pages found in configuration.")
            return

        logger.info(f"Found {len(pages)} pages.")

        # Download Images
        tasks = []
        file_map = {}
        async with httpx.AsyncClient() as client:
            for i, page in enumerate(pages):
                page_num = i + 1
                suffix = page.get('l', page.get('n'))
                
                # Handle list type suffix
                if isinstance(suffix, list):
                    suffix = suffix[0] if suffix else None
                
                if not suffix: continue

                if suffix.startswith('http'):
                    url = suffix
                elif suffix.startswith('files/'):
                    url = f"http://online.fliphtml5.com/{book_id}/{suffix}"
                else:
                    url = f"http://online.fliphtml5.com/{book_id}/files/large/{suffix}"
                
                # Cleanup path
                url = url.replace("/./", "/")
                
                ext = ".webp" if url.lower().endswith(".webp") else ".jpg"
                fname = f"{page_num:04d}{ext}"
                fpath = os.path.join(temp_dir, fname)
                file_map[page_num] = fpath
                tasks.append(download_image(client, url, fpath))
            
            await asyncio.gather(*tasks)

        # Convert to PDF
        valid_files = [file_map[k] for k in sorted(file_map) if os.path.exists(file_map[k])]
        if not valid_files:
            logger.error("No images downloaded.")
            return

        logger.info(f"Converting {len(valid_files)} images to PDF...")
        final_images = []
        for img in valid_files:
            if img.lower().endswith('.webp'):
                try:
                    png = img.replace('.webp', '.png')
                    with Image.open(img) as im:
                        im.save(png, 'PNG')
                    final_images.append(png)
                except:
                    final_images.append(img)
            else:
                final_images.append(img)

        with open(output_path, "wb") as f:
            f.write(img2pdf.convert(final_images))
        
        logger.info(f"PDF Saved: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python downloader.py <book_url_or_id>")
        sys.exit(1)
    
    book_id = sys.argv[1]
    output = "book.pdf"
    asyncio.run(download_fliphtml5(book_id, output))
