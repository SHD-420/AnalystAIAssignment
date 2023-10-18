from bs4 import BeautifulSoup
from requests import get, ConnectionError, Response
from csv import DictWriter
import re

BASE_URL = "https://www.amazon.in"


def fetch(url: str):
    """
    Make get request to a url and get response meanwhile handling errors. 
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'
        }
        res = get(url, headers=headers)

    except ConnectionError:
        print("ERROR! CONNECTION FAILED!")
        return
    except:
        print("UNKNOWN ERROR!")
        return

    if res.status_code != 200:
        print(f"ERROR! REQUEST UNSUCCESSFULL WITH CODE {res.status_code}!")
        return

    return res


def scrape_product_listing(response: Response) -> tuple[list[dict], str]:
    """
    Scrape the following details from product listing page (mentioned as dictionary keys):
    'url', 'name', 'price', 'rating', 'reviews_count'.
    And return the scrapped data as dictionary along with url of next page.
    """

    products: list[dict] = []

    soup = BeautifulSoup(response.text, 'html.parser')
    items = soup.select("[data-component-type=\"s-search-result\"]")

    for item in items:
        try:
            product = {}
            # derrive product url and name from the title element "h2"
            title_element = item.select_one("h2")

            product['url'] = BASE_URL + title_element.select_one('a').attrs['href']
            product['name'] = title_element.text

            # remove commas(,) and convert to float for price; eg. '5,523.31' --> 5523.31
            product['price'] = float(item.select_one(
                'span.a-price-whole').text.replace(',', ''))

            # derrive rating and review count from 2 adjacent spans with aria-label mentioned
            spans = item.select('span[aria-label]')

            for index, span_element in enumerate(spans):
                # regular exp to test if span_element is the rating element
                regexp = re.compile("(^([0-9]*[.])?[0-9]+) out of 5 stars")
                matches = re.findall(regexp, span_element.text)

                # it is not the right rating span elment, continue to next one
                if not len(matches):
                    continue

                product['rating'] = float(matches[0][0])

                # review count elment is always the next span to rating element
                product['review_count'] = int(
                    spans[index+1].attrs['aria-label'].replace(',', ''))

                break

            else:
                # rating and review not found on product
                product['rating'] = 0
                product['review_count'] = 0

            products.append(product)
        
        # simply skip product when any of details are not found
        except AttributeError:
            continue

    # derrive url of next page
    pagination_items = soup.select(
        '.s-pagination-container .s-pagination-item')

    if not len(pagination_items):
        # no pagination item found, therefore no next page
        return products, None

    if pagination_items[-1].name != 'a':
        # last pagination item not an 'a' tag, so no 'next' link
        return products, None

    next_page_url = BASE_URL + pagination_items[-1].attrs['href']

    return products, next_page_url


def scrape_product_page(response: Response):
    """
    Scrape the following details from product page (mentioned as dictionary keys):
    'dimensions', 'asin', 'manufacturer'
    """
    data = {}
    soup = BeautifulSoup(response.text, "html.parser")
    product_detail_element = soup.select_one(
        "[data-feature-name=\"detailBullets\"] ul")

    # in some cases product detail element is not found where expected,
    # we simply skip those products here
    if product_detail_element is None:
        return None

    for li in product_detail_element.findAll("li"):
        # Product dimensions, ASIN and Manufacturer are found as list items' children
        # eg: (where KEY corresponds to Product dimensions, ASIN or Manufacturer)
        # <li>
        #  <span>
        #   <span> {{ KEY }} </span>
        #   <span> {{ VALUE }} </span>
        #  </span>
        # </li>
        spans = li.find("span").findAll("span")

        if "Product Dimensions" in spans[0].text:
            data['dimensions'] = spans[1].text.strip()

        if "ASIN" in spans[0].text:
            data['asin'] = spans[1].text.strip()

        if "Manufacturer" in spans[0].text:
            data['manufacturer'] = spans[1].text.strip()

    return data


def main():

    # Open the 2 files and initialize csv writers for both
    product_list_page_csv = open(
        "product_list.csv", mode="w", encoding="utf-8")
    product_page_csv = open("product.csv", mode="w", encoding="utf-8")

    product_list_page_writer = DictWriter(
        product_list_page_csv,
        fieldnames=['url', 'name', 'price', 'rating', 'review_count']
    )
    product_list_page_writer.writeheader()

    product_page_writer = DictWriter(
        product_page_csv,
        fieldnames=['name', 'dimensions', 'asin', 'manufacturer']
    )
    product_page_writer.writeheader()

    # keep track and limit the number of product listing and product pages fetched
    product_list_pages_fetched = 0
    product_pages_fetched = 0
    url = "https://www.amazon.in/s?k=bags&crid=2M096C61O4MLT&qid=1653308124&sprefix=ba%2Caps%252"

    while product_list_pages_fetched < 20:
        product_list_pages_fetched += 1
        print(f"{product_list_pages_fetched} product lists fetched!")
        data = fetch(url)

        if data is None:
            break

        products, next_pg_url = scrape_product_listing(data)
        product_list_page_writer.writerows(products)

        if next_pg_url is None:
            break
        url = next_pg_url

        for product in products:
            # don't fetch more than 200 product (detail) pages
            if product_pages_fetched >= 200:
                break

            data = fetch(product['url'])

            if data is None:
                continue
            
            product_details = scrape_product_page(data)

            if product_details is None:
                continue
            product_pages_fetched += 1

            product_details['name'] = product['name']
            product_page_writer.writerow(product_details)

    product_page_csv.close()
    product_list_page_csv.close()


if __name__ == "__main__":
    main()
