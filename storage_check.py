import csv
import requests
import threading
from queue import Queue, Empty
from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


HEADERS = {
    # pseudo-headers like :method / :scheme / :path / :authority are implicit in requests
    "Accept":           "application/json, text/plain, */*",
    "Accept-Encoding":  "gzip, deflate, br, zstd",
    "Accept-Language":  "en-US,en;q=0.9,ja-JP;q=0.8,ja;q=0.7",
    "Referer":          "https://support.hp.com/us-en/check-warranty",
    "Origin":           "https://support.hp.com",
    "DNT":              "1",
    "Priority":         "u=1, i",
    "Sec-CH-UA":        '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Linux"',
    "Sec-Fetch-Dest":   "empty",
    "Sec-Fetch-Mode":   "cors",
    "Sec-Fetch-Site":   "same-origin",
    "User-Agent":       "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
                        " (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

def selenium_get_data(driver,url):
    driver.get(url)
    wait = WebDriverWait(driver, timeout=10)
    specs_el = wait.until(
        EC.presence_of_element_located((By.CLASS_NAME, "product-spec"))
    )
    button = driver.find_element(By.ID, "Viewfull")

    button.click()
    html = specs_el.get_attribute('innerHTML')
    soup = BeautifulSoup(html, 'html.parser')

    # Parse all spec-content entries
    specs = {}
    for content in soup.find_all('div', class_='spec-content'):
        title_div = content.find('div', class_='spec-title')
        if not title_div:
            continue
        title = title_div.get_text(strip=True)
        # The description text is inside a nested div
        desc_div = content.find('div', class_='desc-text-non-view-encapsulation')
        value = desc_div.get_text(strip=True) if desc_div else ''
        specs[title] = value
    return specs

    # driver.implicitly_wait(10)
    # 
    # specs = driver.find_element(By.CLASS_NAME, "product-spec")
    # return specs

def build_url(response_json):
    """
    Given the warranty-check JSON response, construct the product details URL.
    """
    data = response_json['verifyResponse']['data']
    friendly_name = data['SEOFriendlyName']
    model_oid = data['productNameOID']
    sku = data['productNumber'].split('#')[0].lower()
    serial = data['serialNumber'].lower()

    return (
        f"https://support.hp.com/us-en/product/details/"
        f"{friendly_name}/model/{model_oid}"
        f"?sku={sku}&serialnumber={serial}"
    )

def get_product_specs(serial, session, driver):
    # Input: Serial number
    # Output: Model number and SKU
    print(serial)
    resp = session.get("https://support.hp.com/us-en/check-warranty")
    resp.raise_for_status()
    html = resp.text
    

    warranty_url = f'https://support.hp.com/wcc-services/searchresult/us-en?q={serial}&context=pdp&authState=anonymous&template=WarrantyLanding'

    
    resp = session.get(warranty_url,headers=HEADERS)
    json = resp.json()
    data = json['data']
    specs_url = build_url(data)
    
    specs = selenium_get_data(driver, specs_url)
    return specs

def worker(queue, lock, writer, headers_list):
    session = requests.Session()
    chrome_opts = Options()
    #chrome_opts.add_argument("--headless")
    #chrome_opts.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=chrome_opts)

    while True:
        try:
            serial = queue.get_nowait()
        except Empty:
            break
        try:
            specs = get_product_specs(serial, session, driver)
        except Exception as e:
            specs = {h: f"ERROR: {e}" for h in headers_list}
        row = [serial] + [specs.get(h, '') for h in headers_list]
        print(row)
        with lock:
            writer.writerow(row)
        queue.task_done()
    driver.quit()
def main(input_path, output_path):
    work_queue = Queue()
    
    with open(input_path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        headers = next(reader)
        if 'serial number' not in [h.lower() for h in headers]:
            f.seek(0)
            reader = csv.reader(f)
        for row in reader:
            try:
                work_queue.put(row[10].strip())
            except Exception as e:# skip rows w/o serial
                pass

    temp_session = requests.Session()
    chrome_opts = Options()
    driver = webdriver.Chrome(options=chrome_opts)
    temp_serial = work_queue.queue.pop()
    first_specs = get_product_specs(temp_serial, temp_session, driver)
    driver.quit()
    spec_titles = list(first_specs.keys()) 
    print(spec_titles)
    time.sleep(4)
    lock = threading.Lock()
    output = open(output_path, 'w', newline='', encoding='utf-8')
    writer = csv.writer(output)
    writer.writerow(['serial']+spec_titles)

    threads = []
    
    for _ in range(4):
        t = threading.Thread(target = worker, args =(work_queue, lock, writer, spec_titles))
        t.start()
        threads.append(t)
        time.sleep(3)
    work_queue.join()

    for t in threads:
        t.join()
    output.close()

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        print("Usage: python hp_warranty_storage.py <serials.csv> <output.csv>")(By.ID, "Viewfull")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])

