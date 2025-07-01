import csv
import requests
from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait


def selenium_get_data(driver,url):
    driver.get(url)
    wait = WebDriverWait(driver, timeout=10)
    wait.until(lambda _ : driver.find_element(By.CLASS_NAME, "device_spec"))
    print(driver)
    time.sleep(10)

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

def get_product_specs(serial, driver):
    # Input: Serial number
    # Output: Model number and SKU
    print(serial)
    session = requests.Session()
    resp = session.get("https://support.hp.com/us-en/check-warranty")
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    headers = {
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

    warranty_url = f'https://support.hp.com/wcc-services/searchresult/us-en?q={serial}&context=pdp&authState=anonymous&template=WarrantyLanding'

    
    resp = session.get(warranty_url,headers=headers)
    json = resp.json()
    data = json['data']
    specs_url = build_url(data)
    
    print(specs_url)
    specs = selenium_get_data(driver, specs_url)
    print(specs)
    time.sleep(10)
    return {''}

def main(csv_path):
    chrome_opts = Options()
    chrome_opts.add_argument("--headless")
    chrome_opts.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=chrome_opts)

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        # Skip header row if present
        headers = next(reader)
        if 'serial number' not in [h.lower() for h in headers]:
            # If no header, reset reader
            f.seek(0)
            reader = csv.reader(f)

        for row in reader:
            serial = row[10].strip()
            try:
                get_product_specs(serial, driver)
            except Exception as e:
                print(f"Error processing {serial}: {e}")


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print("Usage: python hp_warranty_storage.py <serials.csv>")
        sys.exit(1)
    main(sys.argv[1])

