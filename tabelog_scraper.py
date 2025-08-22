import requests
from bs4 import BeautifulSoup

def scrape_tabelog(url):
    """Scrape Tabelog restaurant data"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        page = requests.get(url, headers=headers)
        page.raise_for_status()
        soup = BeautifulSoup(page.text, "html.parser")

        name_tag = soup.find("h2", class_="rstinfo-table__name-wrap")
        if not name_tag:
            name_tag = soup.find("h2", class_="display-name")
        name = name_tag.get_text(strip=True) if name_tag else None

        rating_tag = soup.find("b", class_="c-rating__val")
        rating = float(rating_tag.get_text(strip=True)) if rating_tag else None

        categories = []
        category_tags = soup.find_all("span", class_="linktree__parent-target-text")
        if not category_tags:
            category_tags = soup.find_all("span", class_="category")
        for tag in category_tags:
            cat_text = tag.get_text(strip=True)
            if cat_text:
                categories.append(cat_text)

        address_tag = soup.find("p", class_="rstinfo-table__address")
        address = address_tag.get_text(strip=True) if address_tag else None

        return {
            "name": name,
            "rating": rating,
            "categories": categories,
            "address": address
        }
    except Exception as e:
        print(f"Error scraping Tabelog: {e}")
        return None 