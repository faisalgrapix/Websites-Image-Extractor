import requests
import time

base = 'https://sangemeel.shop'
page = 1
urls = []

while True:
    r = requests.get(f'{base}/products.json?limit=250&page={page}', timeout=20)
    products = r.json().get('products', [])
    if not products:
        break
    for p in products:
        urls.append(f'{base}/products/{p["handle"]}')
    print(f'Page {page}: {len(products)} products, total: {len(urls)}')
    if len(products) < 250:
        break
    page += 1
    time.sleep(0.5)

with open('product_urls.txt', 'w') as f:
    f.write('\n'.join(urls))

print(f'Done. Saved {len(urls)} URLs to product_urls.txt')