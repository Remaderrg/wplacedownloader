import os
import time
from PIL import Image
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import base64

url = "https://backend.wplace.live/files/s0/tiles/"

def get_inclusive_range(a, b):
    start = min(a, b)
    end = max(a, b)
    return range(start, end + 1)

def save_tile_from_browser(url, x, y, save_dir, page, max_retries=3):
    tile_url = f"{url}{x}/{y}.png"
    filename = os.path.join(save_dir, f"tile_{x}_{y}.png")
    if os.path.exists(filename):
        print(f"File already exists: {filename}, skipping download.")
        return True, False
    for attempt in range(1, max_retries + 1):
        page.goto(tile_url)
        js = '''() => {
            const img = document.querySelector('img') || document.querySelector('body > img') || document.querySelector('body > image');
            if (!img) return null;
            const canvas = document.createElement('canvas');
            canvas.width = img.naturalWidth;
            canvas.height = img.naturalHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0);
            return canvas.toDataURL('image/png').split(',')[1];
        }'''
        b64 = page.evaluate(js)
        if b64:
            with open(filename, 'wb') as f:
                import base64
                f.write(base64.b64decode(b64))
            print(f"Saved: {filename}")
            return True, True
        else:
            print(f"Attempt {attempt}: failed to get image {tile_url} via JS!")
            if attempt < max_retries:
                time.sleep(1)  # small delay between attempts
    print(f"Failed to download {tile_url} after {max_retries} attempts!")
    return False, False

def stitch_tiles(x1, y1, x2, y2, save_dir):
    x_values = list(get_inclusive_range(x1, x2))
    y_values = list(get_inclusive_range(y1, y2))  # smaller Y values will be on top
    tiles = []
    for y in y_values:
        row = []
        for x in x_values:
            filename = os.path.join(save_dir, f"tile_{x}_{y}.png")
            if os.path.exists(filename):
                row.append(Image.open(filename))
            else:
                row.append(None)
        if any(row):
            tiles.append(row)
    if not tiles or not any(tiles[0]):
        raise ValueError("Could not find any downloaded tiles. Check coordinates and file availability.")
    first_tile = next(tile for tile in tiles[0] if tile)
    tile_w, tile_h = first_tile.size
    result_img = Image.new('RGBA', (tile_w * len(x_values), tile_h * len(y_values)))
    for row_idx, row in enumerate(tiles):
        for col_idx, tile in enumerate(row):
            if tile:
                result_img.paste(tile, (col_idx * tile_w, row_idx * tile_h))
    return result_img

def main():
    output_filename = input("Enter output filename: ")
    if not (output_filename.lower().endswith('.png') or output_filename.lower().endswith('.jpg') or output_filename.lower().endswith('.jpeg')):
        output_filename += '.png'
    x1 = int(input("Enter coordinate x1: "))
    y1 = int(input("Enter coordinate y1: "))
    x2 = int(input("Enter coordinate x2: "))
    y2 = int(input("Enter coordinate y2: "))
    print(f"Output file: {output_filename}")
    print(f"Rectangle points: ({x1}, {y1}) and ({x2}, {y2})")

    save_dir = "tiles_tmp"
    os.makedirs(save_dir, exist_ok=True)
    x_values = list(get_inclusive_range(x1, x2))
    y_values = list(get_inclusive_range(y1, y2))
    with sync_playwright() as p:
        def launch():
            b = p.chromium.launch(headless=False)
            page = b.new_page()
            try:
                page.set_default_navigation_timeout(10000)
                page.set_default_timeout(10000)
            except Exception:
                pass
            return b, page

        browser, page = launch()
        try:
            for y in y_values:
                for x in x_values:
                    restart_attempts = 0
                    while True:
                        try:
                            success, downloaded_now = save_tile_from_browser(url, x, y, save_dir, page)
                            if success and downloaded_now:
                                time.sleep(1)
                            break
                        except PlaywrightTimeoutError:
                            print("Page load timeout. Restarting browser and continuing...")
                            try:
                                browser.close()
                            except Exception:
                                pass
                            browser, page = launch()
                            restart_attempts += 1
                            if restart_attempts >= 3:
                                print(f"Skipping tile {x},{y} after 3 restarts.")
                                break
        finally:
            try:
                browser.close()
            except Exception:
                pass
    try:
        result_img = stitch_tiles(x1, y1, x2, y2, save_dir)
        result_img.save(output_filename)
        print(f"Image saved to {output_filename}")
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
